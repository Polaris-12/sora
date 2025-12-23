import os
import time
import json
import requests
import folder_paths

def _parse_image_urls(value):
    if isinstance(value, (list, tuple)):
        return [v for v in value if v]
    raw = value or ""
    parts = []
    for line in raw.replace(",", "\n").splitlines():
        s = line.strip()
        if s:
            parts.append(s)
    return parts

def _extract_video_url(data):
    if not isinstance(data, dict):
        return ""
    if data.get("video_url"):
        return data["video_url"]
    detail = data.get("detail") or {}
    if detail.get("url"):
        return detail["url"]
    if detail.get("downloadable_url"):
        return detail["downloadable_url"]
    return ""

class SoraCreateFetchVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_base": ("STRING", {"default": "https://manju.chat"}),
                "api_key": ("STRING", {"default": "", "multiline": False}),
                "images": ("STRING", {"multiline": True, "default": ""}),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "resolution": (["small", "large"], {"default": "small"}),
                "duration": ("INT", {"default": 10, "min": 1, "max": 60}),
            },
            "optional": {
                "orientation": (["portrait", "landscape"], {"default": "portrait"}),
                "model": ("STRING", {"default": "sora-2"}),
                "watermark": ("BOOLEAN", {"default": False}),
                "origin": ("STRING", {"default": "https://web.apiplus.org"}),
                "referer": ("STRING", {"default": "https://web.apiplus.org/"}),
                "user_agent": ("STRING", {"default": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"}),
                "poll_interval": ("INT", {"default": 5, "min": 1, "max": 60}),
                "max_wait": ("INT", {"default": 600, "min": 10, "max": 3600}),
            }
        }

    RETURN_TYPES = ("VIDEO", "STRING", "STRING")
    RETURN_NAMES = ("video", "video_path", "video_url")
    FUNCTION = "run"
    CATEGORY = "Sora"

    def run(
        self,
        api_base,
        api_key,
        images,
        prompt,
        resolution,
        duration,
        orientation="portrait",
        model="sora-2",
        watermark=False,
        origin="https://web.apiplus.org",
        referer="https://web.apiplus.org/",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        poll_interval=5,
        max_wait=600,
    ):
        image_urls = _parse_image_urls(images)
        if not image_urls:
            raise ValueError("images is empty. Provide one or more image URLs.")

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        key = api_key.strip() or os.environ.get("SORA_API_KEY", "")
        if key:
            headers["Authorization"] = "Bearer " + key
        if origin:
            headers["Origin"] = origin
        if referer:
            headers["Referer"] = referer
        if user_agent:
            headers["User-Agent"] = user_agent

        payload = {
            "images": image_urls,
            "model": model,
            "orientation": orientation,
            "prompt": prompt,
            "size": resolution,
            "duration": int(duration),
            "watermark": bool(watermark),
        }

        base = api_base.rstrip("/")
        create_url = base + "/v1/video/create"
        query_url = base + "/v1/video/query"

        resp = requests.post(create_url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        create_data = resp.json()
        task_id = create_data.get("id")
        if not task_id:
            raise RuntimeError("Create response missing id: " + json.dumps(create_data, ensure_ascii=True))

        start = time.time()
        last = None
        while True:
            q = requests.get(query_url, params={"id": task_id}, headers=headers, timeout=60)
            q.raise_for_status()
            last = q.json()
            status = last.get("status") or (last.get("detail") or {}).get("status")
            if status in ("completed", "succeeded", "success", "done"):
                break
            if status in ("failed", "error", "canceled", "cancelled"):
                raise RuntimeError("Sora task failed: " + json.dumps(last, ensure_ascii=True))
            if time.time() - start > max_wait:
                raise RuntimeError("Sora task timeout after %ss. last=%s" % (max_wait, json.dumps(last, ensure_ascii=True)))
            time.sleep(int(poll_interval))

        video_url = _extract_video_url(last)
        if not video_url:
            raise RuntimeError("Missing video_url in response: " + json.dumps(last, ensure_ascii=True))

        output_dir = folder_paths.get_output_directory()
        subfolder = "sora"
        os.makedirs(os.path.join(output_dir, subfolder), exist_ok=True)
        safe_task = task_id.replace(":", "_")
        filename = "sora_%s.mp4" % safe_task
        filepath = os.path.join(output_dir, subfolder, filename)

        with requests.get(video_url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

        video = {"filename": filename, "subfolder": subfolder, "type": "output"}
        return (video, filepath, video_url)

NODE_CLASS_MAPPINGS = {
    "SoraCreateFetchVideo": SoraCreateFetchVideo,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SoraCreateFetchVideo": "Sora Create + Fetch Video (External API)",
}
