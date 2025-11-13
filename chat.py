import time, re, sys, json, requests, argparse



OLLAMA_BASE_URL = "http://192.168.86.114:11434"
GENERATE_URL = f'{OLLAMA_BASE_URL}/api/generate'



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

async def send_prompt_http(prompt, model="qwen3-coder:30b", callback=None):
    streamingIndex = 0
    payload = {"model": model, "prompt": prompt, "stream": True}
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
                chunk = extract_text(j)
            except Exception:
                chunk = line
            if chunk:
                if callback:
                    if total_text != "":
                        if time.time() - streamingIndex > 1:
                            streamingIndex = time.time()
                            await callback(content=f'{total_text}...')
                else:
                    print(chunk, end="", flush=True)
                total_text += chunk
                w, t = count_words_and_tokens(chunk)
                total_words += w
                total_tokens += t
    finally:
        if start is None:
            print("no response")
            return None
        
        elapsed = time.time() - start
        if elapsed <= 0:
            elapsed = 1e-6
        wpm = (total_words / elapsed) * 60
        tps = (total_tokens / elapsed)
        print("\n\n--- stats ---")
        print(f'time elapsed: {elapsed:.3f} s')
        print(f'words prodused: {total_words}, WPM {wpm:.1f}')
        print(f'Tokens (heuristic): {total_tokens}, Tokens/s: {tps:.2f}')
    return {
        "text": total_text,
        "seconds": elapsed,
        "words": total_words,
        "tokens": total_tokens,
        "wpm": wpm,
        "tps": tps
    }


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