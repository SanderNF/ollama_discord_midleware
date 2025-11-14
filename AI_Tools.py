import aiohttp
import asyncio
import json
import time
import aiohttp
from urllib.parse import quote_plus
from chat import saveOnDone, responseInfo




async def perform_search(query, max_results=3):
    print(f'search was called: \n{query} \n{max_results}')
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote_plus(query)}&format=json&srlimit={max_results}&utf8=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return f"Wikipedia search error: {resp.status} {resp.reason}"
            data = await resp.json()
            results = [item["snippet"] for item in data.get("query", {}).get("search", [])]
            return "\n".join(results) or "No search results found."
        


SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_tool",
        "description": "Get factual information for a query using DuckDuckGo or fallback to Wikipedia.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up."
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 3
                }
            },
            "required": ["query"]
        }
    }
}

OLLAMA_CHAT_URL = "http://192.168.86.114:11434/api/chat"

async def preRunAgent(prompt, model="sam860/lucy:1.7b", callback=None, payload={}, recusion=0):
    streamingIndex = 0
    """
    Send prompt using POST /api/chat with Ollama tool calling.
    """
    if payload == {}:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system", 
                    "content": "your task is to collect any usefull data to pass onto a larger LLM for post prossesing"
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "tools": [SEARCH_TOOL],
            "stream": True
        }

    total_text = ""
    start_time = None

    async with aiohttp.ClientSession() as session:
        async with session.post(OLLAMA_CHAT_URL, json=payload) as resp:
            async for raw_line in resp.content:
                try:
                    line = raw_line.decode("utf-8").strip()
                    if not line or line == "[done]":
                        break
                    if line.startswith("data:"):
                        line = line[len("data:"):].strip()
                except Exception:
                    continue

                if start_time is None and line:
                    start_time = time.time()

                try:
                    j = json.loads(line)
                    saveOnDone(j)
                except Exception:
                    continue

                # Check for tool calls in this chunk
                tool_calls = j.get("message", {}).get("tool_calls", [])
                for call in tool_calls:
                    if call.get("function", {}).get("name") == "search_tool" and (recusion < 1):
                        args = call["function"].get("arguments", {})
                        query = args.get("query", "")
                        max_results = args.get("max_results", 3)
                        # Perform the search using your existing function
                        results = await perform_search(query, max_results=max_results)
                        print(results)
                        # Inject the results back as a system message
                        followup_msg = {
                            "role": "tool",
                            "content": f'results from search: {results}'
                        }
                        # Send it back to Ollama to continue the conversation
                        payload["messages"].append(followup_msg)
                        return await preRunAgent(None, model=model, callback=callback, payload=payload, recusion=recusion+1)
                        """async with session.post(OLLAMA_CHAT_URL, json={
                            "model": model,
                            "messages": [followup_msg],
                            "stream": True,
                            "tools": [SEARCH_TOOL]
                        }) as followup_resp:
                            async for f_line in followup_resp.content:
                                f_line = f_line.decode("utf-8").strip()
                                if f_line.startswith("data:"):
                                    f_line = f_line[len("data:"):].strip()
                                try:
                                    f_j = json.loads(f_line)
                                    chunk = f_j.get("message", {}).get("content", "")
                                    total_text += chunk
                                    if callback:
                                        await callback(total_text)
                                except Exception:
                                    continue"""

                # Regular assistant message
                chunk = j.get("message", {}).get("content", "")
                #print(chunk)
                total_text += chunk
                if callback:
                    if time.time() - streamingIndex > 1:
                        streamingIndex = time.time()
                        await callback(content=f'{total_text}...')

    elapsed = time.time() - (start_time or time.time())
    words = len(total_text.split())
    tokens = len(total_text.split())  # simple heuristic
    wpm = (words / elapsed) * 60
    tps = tokens / elapsed


    metricData = responseInfo.returned_data
    print(metricData)

    EPS = metricData["eval_count"] / (metricData["eval_duration"] / 1000000000)
    PEPS = metricData["prompt_eval_count"] / (metricData["prompt_eval_duration"] / 1000000000)
    WPM = (words / (metricData["eval_duration"] / 1000000000)) * 60
    WPS = (words / (metricData["eval_duration"] / 1000000000))

    formatted_response = (
            f"{total_text}\n\n\n"
            f"> Total time: {(metricData["total_duration"]/ 1000000000):.2f}\n"
            f"> Model load time: {(metricData["load_duration"]/ 1000000000):.2f}\n"
            f"> Read prompt time: {(metricData["prompt_eval_duration"]/ 1000000000):.2f}\n"
            f"> Generation time: {(metricData["eval_duration"]/ 1000000000):.2f}\n"
            f"> Words: {words}\n"
            f"> Tokens: {tokens}\n"
            f"> WPM: {wpm:.2f}\n"
            f"> TPS: {tps:.2f}\n"
            f"> Device: CPU\n"
            f"> Model: {metricData["model"]}\n"
        )
    if callback:
        streamingIndex = time.time()
        await callback(content=f'{formatted_response}')
    return {
        "text": total_text,
        "seconds": elapsed,
        "words": words,
        "tokens": tokens,
        "wpm": wpm,
        "tps": tps
    }



async def main():
    print(await preRunAgent(input("Pre-run prompt> ")))

if __name__ == "__main__":
    while True:
        asyncio.run(main())
        