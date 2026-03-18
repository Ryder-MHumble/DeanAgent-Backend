"""
AsyncAPIClient - 统一的异步 API 客户端

消除重复：
- HTTP 请求封装
- 速率限制
- 重试逻辑
- 缓存支持
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx


class AsyncAPIClient:
    """异步 API 客户端（带速率限制和缓存）"""

    def __init__(
        self,
        base_url: str = "",
        headers: dict[str, str] | None = None,
        rate_limit: float = 0.5,
        timeout: float = 30.0,
        cache_dir: Path | str | None = None,
    ):
        self.base_url = base_url
        self.headers = headers or {}
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.logger = logging.getLogger(self.__class__.__name__)

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        use_cache: bool = False,
        cache_key: str | None = None,
    ) -> dict | list | None:
        """GET 请求"""
        full_url = f"{self.base_url}{url}" if not url.startswith("http") else url

        # 检查缓存
        if use_cache and cache_key and self.cache_dir:
            cached = self._load_cache(cache_key)
            if cached is not None:
                self.logger.debug(f"缓存命中: {cache_key}")
                return cached

        # 速率限制
        await asyncio.sleep(self.rate_limit)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(full_url, params=params, headers=self.headers)
                response.raise_for_status()
                data = response.json()

                # 保存缓存
                if use_cache and cache_key and self.cache_dir:
                    self._save_cache(cache_key, data)

                return data

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP 错误 {e.response.status_code}: {full_url}")
            return None
        except Exception as e:
            self.logger.error(f"请求失败: {e}")
            return None

    async def post(
        self,
        url: str,
        payload: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict | list | None:
        """POST 请求"""
        full_url = f"{self.base_url}{url}" if not url.startswith("http") else url

        # 速率限制
        await asyncio.sleep(self.rate_limit)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    full_url, data=payload, json=json_data, headers=self.headers
                )
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP 错误 {e.response.status_code}: {full_url}")
            return None
        except Exception as e:
            self.logger.error(f"请求失败: {e}")
            return None

    def _load_cache(self, key: str) -> dict | list | None:
        """加载缓存"""
        cache_file = self.cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"缓存加载失败: {e}")
            return None

    def _save_cache(self, key: str, data: dict | list):
        """保存缓存"""
        cache_file = self.cache_dir / f"{key}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning(f"缓存保存失败: {e}")


class AMinerClient(AsyncAPIClient):
    """AMiner API 客户端（预配置）"""

    def __init__(self, api_key: str, cache_dir: Path | str = "data/cache/aminer"):
        super().__init__(
            base_url="https://api.aminer.cn/api",
            headers={"Authorization": f"Bearer {api_key}"},
            rate_limit=0.5,
            cache_dir=cache_dir,
        )

    async def search_organizations(self, name: str) -> list[dict]:
        """搜索机构"""
        data = await self.get(
            "/org/search", params={"query": name}, use_cache=True, cache_key=f"org_{name}"
        )
        return data.get("data", []) if data else []

    async def search_scholars(self, name: str, org: str | None = None) -> list[dict]:
        """搜索学者"""
        params = {"query": name}
        if org:
            params["org"] = org

        data = await self.get("/person/search", params=params)
        return data.get("data", []) if data else []

    async def get_scholar_detail(self, aminer_id: str) -> dict | None:
        """获取学者详情"""
        data = await self.get(
            f"/person/{aminer_id}", use_cache=True, cache_key=f"scholar_{aminer_id}"
        )
        return data.get("data") if data else None
