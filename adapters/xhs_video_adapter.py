"""视频获取适配器：yt-dlp 优先，XHS-Downloader 兜底，全部失败则停止。

约束（config/xhs_readonly_policy.yaml）：
- 仅通过 CLI 调用外部工具，不复制任何 GPL 项目源码；
- 视频文件只允许保存到 tmp/ 目录（tmp_only），不提交 Git；
- 不得绕过验证码/风控；工具不可用时如实报错。
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from src.video_models import VideoAsset


class VideoAcquisitionFailed(Exception):
    """两种获取方式均失败。"""


class StoragePolicyViolation(Exception):
    """视频存储路径违反 tmp_only 策略。"""


Runner = Callable[..., subprocess.CompletedProcess]


def ensure_tmp_storage(out_dir: str | Path) -> Path:
    """强制视频输出目录位于 tmp/ 下。"""
    path = Path(out_dir).resolve()
    if "tmp" not in [p.lower() for p in path.parts]:
        raise StoragePolicyViolation(f"视频仅允许保存到 tmp/ 目录: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def find_tool(name: str) -> Optional[str]:
    """定位外部 CLI（不存在则返回 None，由调用方如实记录）。"""
    return shutil.which(name)


def acquire_with_ytdlp(
    url: str, out_dir: Path, runner: Runner = subprocess.run
) -> Optional[Path]:
    """yt-dlp 获取公开视频。失败返回 None。"""
    tool = find_tool("yt-dlp")
    if not tool:
        return None
    out_tpl = str(out_dir / "%(id)s.%(ext)s")
    proc = runner(
        [tool, "--no-playlist", "-f", "best", "-o", out_tpl, url],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    if proc.returncode != 0:
        return None
    files = sorted(out_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    videos = [f for f in files if f.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"}]
    return videos[0] if videos else None


def acquire_with_xhs_downloader(
    url: str, out_dir: Path, runner: Runner = subprocess.run
) -> Optional[Path]:
    """XHS-Downloader 外部 CLI 兜底（GPL-3.0，仅 CLI 调用）。失败返回 None。"""
    tool = find_tool("XHS-Downloader") or find_tool("xhs-downloader")
    if not tool:
        return None
    proc = runner(
        [tool, "--url", url, "--work_path", str(out_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    if proc.returncode != 0:
        return None
    files = sorted(out_dir.rglob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    videos = [f for f in files if f.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"}]
    return videos[0] if videos else None


def acquire_video(
    url: str,
    out_dir: str | Path = "tmp/xhs_video",
    runner: Runner = subprocess.run,
) -> VideoAsset:
    """按策略顺序获取视频：yt-dlp → XHS-Downloader → 停止。"""
    target = ensure_tmp_storage(out_dir)
    errors: list[str] = []

    path = acquire_with_ytdlp(url, target, runner)
    if path:
        return VideoAsset(
            source_url=url,
            local_path=str(path),
            acquired_by="yt-dlp",
            acquired_at=datetime.now(timezone.utc).isoformat(),
        )
    errors.append("yt-dlp 不可用或获取失败")

    path = acquire_with_xhs_downloader(url, target, runner)
    if path:
        return VideoAsset(
            source_url=url,
            local_path=str(path),
            acquired_by="xhs-downloader",
            acquired_at=datetime.now(timezone.utc).isoformat(),
        )
    errors.append("XHS-Downloader 不可用或获取失败")

    raise VideoAcquisitionFailed(
        "；".join(errors) + "。按策略停止，不尝试绕过验证码/风控"
    )
