import time, re, sys, json, requests, argparse



OLLAMA_BASE_URL = "http://192.168.86.114:11434"
GENERATE_URL = f'{OLLAMA_BASE_URL}/api/generate'


class responseInfo:
    returned_data= {}
    model: str = ""
    created_At: str = ""
    response: str = ""
    done: bool = False
    done_Reason: str = ""
    total_Duration: int = 0
    load_Duration: int = 0
    prompt_Eval_Count: int = 0
    prompt_Eval_Duration: int = 0
    eval_Count: int = 0
    eval_Duration: int = 0
    context: object = []


def extract_text(obj):
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        for k in ("content", "text", "message", "response"):
            if k in obj and isinstance(obj[k], (str,)):
                return obj[k]
        
        s = ""
        for v in obj.values():
            s += extract_text(v)
        return s
    if isinstance(obj, list):
        return "".join(extract_text(v) for v in obj)
    return ""

def count_words_and_tokens(text):
    words = re.findall(r"\b\w+\b", text)

    tokens = re.findall(r"\S+", text)
    return len(words), len(tokens)

def saveOnDone(data):
    if data["done"]:
        print("streaming is done")
        #print(data)
        responseInfo.returned_data = data
        for key, value in data.items():
            if hasattr(responseInfo, key):
                setattr(responseInfo, key, value)
    else:
        #print("still streaming")
        return

async def send_prompt_http(prompt, model, callback=None):
    streamingIndex = 0
    payload = {"model": model, "prompt": prompt, "stream": True}
    print(payload)
    try:
        resp = requests.post(GENERATE_URL, json=payload, stream=True, timeout=60)
    except Exception as e:
        print(f'HTTP request faild: {e}')
        return None
    

    total_text = ""
    total_words = 0
    total_tokens = 0
    start = None
    try:
        for raw_line in resp.iter_lines():
            if not raw_line:
                continue
            try:
                line = raw_line.decode('utf-8').strip()
                if line.startswith("data:"):
                    line = line[len("data:"):].strip
                if line == "[done]":
                    break

                if start is None and line:
                    start = time.time()
            except UnicodeDecodeError as e:
                print(f'Error decoding response: {e}')
                continue
            chunk = ""
            try:
                j = json.loads(line)
                #print(j)
                saveOnDone(j)
                chunk = extract_text(j)
            except Exception:
                chunk = line
            if chunk:
                if callback:
                    if total_text != "":
                        if time.time() - streamingIndex > 1:
                            try:
                                streamingIndex = time.time()
                                await callback(content=f'{total_text}...')
                            except Exception as e:
                                if "(error code: 50035): Invalid Form Body" in str(e):
                                    print("max msg limit reached")
                                    resp.close()
                                raise Exception(f"max discord msg limit reached! \nError: {str(e)}")
                else:
                    print(chunk, end="", flush=True)
                total_text += chunk
                w, t = count_words_and_tokens(chunk)
                total_words += w
                total_tokens += t
    finally:
        # ensure the response is closed but do not return from inside finally
        if 'resp' in locals():
            try:
                resp.close()
            except Exception:
                pass

    if start is None:
        print("no response")
        return None


    elapsed = time.time() - start
    if elapsed <= 0:
        elapsed = 1e-6
    wpm = (total_words / elapsed) * 60
    tps = (total_tokens / elapsed)
    
    """
    # Parse the JSON response
    response_data = resp.json()

    if response_data["done"]:
        print("done")
        print(response_data)

        # Extract token information from the response
        total_tokens = response_data.get("eval_count", 0)
        eval_duration = response_data.get("eval_duration", 0)

        # Convert nanoseconds to seconds
        eval_duration_seconds = eval_duration / 1_000_000_000

        # Calculate tokens per second
        tps = total_tokens / eval_duration_seconds if eval_duration_seconds > 0 else 0

        # Extract other information
        response_text = response_data.get("response", "")
        total_words = len(response_text.split()) if response_text else 0

        # Print stats
        print("\n\n--- stats ---")
        print(f'time elapsed: {eval_duration_seconds:.3f} s')
        print(f'words produced: {total_words}, WPM {0:.1f}')  # WPM calculation requires prompt tokens and time
        print(f'Tokens (heuristic): {total_tokens}, Tokens/s: {tps:.2f}')

        # Return the structured data
        return {
            "text": response_text,
            "seconds": eval_duration_seconds,
            "words": total_words,
            "tokens": total_tokens,
            "wpm": 0,  # WPM calculation requires prompt tokens and time
            "tps": tps
        }"""
    """print(
        responseInfo.model,
        responseInfo.created_At,
        responseInfo.response,
        responseInfo.done,
        responseInfo.done_Reason,
        responseInfo.total_Duration,
        responseInfo.load_Duration,
        responseInfo.prompt_Eval_Count,
        responseInfo.prompt_Eval_Duration,
        responseInfo.eval_Count,
        responseInfo.eval_Duration
    )"""
    #print(responseInfo.returned_data)
    metricData = responseInfo.returned_data

    EPS = metricData["eval_count"] / (metricData["eval_duration"] / 1000000000)
    PEPS = metricData["prompt_eval_count"] / (metricData["prompt_eval_duration"] / 1000000000)
    WPM = (total_words / (metricData["eval_duration"] / 1000000000)) * 60
    WPS = (total_words / (metricData["eval_duration"] / 1000000000))
    
    print("\n\n--- stats ---")
    print(f'time elapsed: {elapsed:.3f} s')
    print(f'words prodused: {total_words}, WPM {wpm:.1f}')
    print(f'Tokens (heuristic): {total_tokens}, Tokens/s: {tps:.1f}')
    print(f'Eval count: {metricData["eval_count"]} Eval\'s/second: {EPS:.1f}')
    print(f'Prompt-Eval count: {metricData["prompt_eval_count"]} Prompt-Eval\'s/second: {PEPS:.1f}')
    print(f'Total duration: {(metricData["total_duration"]/ 1000000000):.3f}')
    print(f'Load duration: {(metricData["load_duration"]/ 1000000000):.3f}')
    print(f'Eval duration: {(metricData["eval_duration"]/ 1000000000):.3f}')
    #print(f'Prompt-Eval duration: {(metricData["prompt_eval_duration"]/ 1000000000):.2f}')
    print(f'WPS: {WPS:.1f} WPM: {WPM:.1f}')
    print(f'Stop reason: {metricData["done_reason"]}')
    return {
        "text": total_text,
        "seconds_total": (metricData["total_duration"]/ 1000000000),
        "seconds_eval": (metricData["eval_duration"]/ 1000000000),
        "seconds_prompt_eval": (metricData["prompt_eval_duration"]/ 1000000000),
        "seconds_load": (metricData["load_duration"]/ 1000000000),
        "words": total_words,
        "tokens": metricData["eval_count"],
        "wpm": wpm,
        "tps": EPS
    }
    """return {
        "text": total_text,
        "seconds": elapsed,
        "words": total_words,
        "tokens": total_tokens,
        "wpm": wpm,
        "tps": tps
    }"""


def main():
    p = argparse.ArgumentParser(description="send prompts to Ollama and print stats.")
    p.add_argument("prompt", nargs="?", help="Inital prompt to send. if omited, enters interactive mode")
    p.add_argument("--model", default="qwen3-coder:30b", help="Model name (defult: qwen3-coder:30b).")
    args = p.parse_args()

    if args.prompt:
        res = send_prompt_http(args.prompt, model=args.model)
        if res is None:
            print("Failed to get response from ollama. Ensure Ollama is runing and the HTTP API is avalibe at:"+ OLLAMA_BASE_URL)
            return
    
    print("\nEnter prompts (type 'exit' or 'quit' to end, or use Ctrl+d):")
    while True:
        try:
            prompt = input("\nPrompt> ").strip()
            if prompt.lower in ['exit','quit']:
                print("goodbye")
                return
            if not prompt:
                print("Please enter a prompt or type 'exit' to quit.")
                continue

            res = send_prompt_http(prompt, model=args.model)
            if res is None:
                print("Failed to get response from ollama. Ensure Ollama is runing and the HTTP API is avalibe at:"+ OLLAMA_BASE_URL)
                break
        
        except EOFError:
            print("\nGoodbye")
            break
        except KeyboardInterrupt:
            print("operation cancelled. Type 'exit' or quit to enter a new prompt.")

if __name__ == "__main__":
    main()