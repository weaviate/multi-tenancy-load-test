import requests
import time


def query(prometheus_url: str, query: str, seconds_ago: int) -> float:
    end_time = time.time()
    start_time = end_time - seconds_ago

    # Convert time to milliseconds and format as strings for Prometheus API
    start_time_str = f"{start_time:.3f}"
    end_time_str = f"{end_time:.3f}"

    query_url = f"{prometheus_url}/api/v1/query_range"
    params = {
        "query": query,
        "start": start_time_str,
        "end": end_time_str,
        "step": "10s",  # This should match the range you are looking over
    }

    response = requests.get(query_url, params=params)
    if response.status_code == 200:
        try:
            result = response.json()
            if len(result["data"]["result"]) > 0:
                values = result["data"]["result"][0]["values"]
                values = [float(tpl[1]) for tpl in values]
                mean = sum(values) / len(values)
                return mean
            else:
                return 0.0
        except Exception as e:
            print(f"Could not parse the response: {e}")
    else:
        print("Failed to query Prometheus:", response.text)
        return 0.0
