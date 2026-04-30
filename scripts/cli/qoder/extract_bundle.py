#!/usr/bin/env python3
r"""
从 Qoder CLI qodercli.exe 提取嵌入的 JS bundle 和资源文件。

qodercli.exe 是 Bun standalone 可执行文件（bun build --compile），
PE 文件的 .bun 节区包含完整 JS 源码和嵌入资源（DLL、native 模块等）。

提取后的 JS 可通过 bun run 直接运行，与原始 exe 功能完全一致。

用法：
  python -m scripts.cli.qoder.extract_bundle                     # 提取 + 配置启动
  python -m scripts.cli.qoder.extract_bundle --target X.exe      # 指定 exe
  python -m scripts.cli.qoder.extract_bundle --output DIR        # 指定输出目录
  python -m scripts.cli.qoder.extract_bundle --no-shim           # 只提取，不配置启动
  python -m scripts.cli.qoder.extract_bundle --uninstall-shim    # 移除启动劫持
"""

from __future__ import annotations

import argparse
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts.shared.patch_utils import init_terminal, print_status

SHIM_MARKER = "# Qoder CLI 汉化版 - 由 AntigravityChinese 自动配置"
SHIM_VERSION_MARKER = "# Qoder CLI 汉化版 - shim v5 utf8-help-decode"
DEFAULT_OUTPUT = Path.home() / ".qoder" / "extracted"
VIRTUAL_ROOT_PREFIX = "B:/~BUN/root/"
VIRTUAL_ROOT_DIR = Path("bunfs") / "~BUN" / "root"

# ---------------------------------------------------------------------------
# exe 路径发现（与 patch_app_zh.py 共享逻辑）
# ---------------------------------------------------------------------------

def discover_target() -> Path:
    """按优先级搜索 qodercli.exe 安装路径。"""
    candidates: list[Path] = []

    qoder_home = os.environ.get("QODER_CLI_HOME")
    if qoder_home:
        candidates.append(Path(qoder_home) / "qodercli.exe")

    candidates.append(
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "nodejs" / "node_modules" / "@qoder-ai" / "qodercli" / "bin" / "qodercli.exe"
    )

    appdata = os.environ.get("APPDATA", "")
    if appdata:
        candidates.append(
            Path(appdata) / "npm" / "node_modules" / "@qoder-ai" / "qodercli" / "bin" / "qodercli.exe"
        )

    nvm_symlink = os.environ.get("NVM_SYMLINK", "")
    if nvm_symlink:
        candidates.append(
            Path(nvm_symlink) / "node_modules" / "@qoder-ai" / "qodercli" / "bin" / "qodercli.exe"
        )

    for c in candidates:
        if c.exists():
            return c

    return candidates[0] if candidates else Path(
        r"C:\Program Files\nodejs\node_modules\@qoder-ai\qodercli\bin\qodercli.exe"
    )


# ---------------------------------------------------------------------------
# PE 解析 + Bundle 提取
# ---------------------------------------------------------------------------

def parse_pe_sections(data: bytes) -> list[dict]:
    """解析 PE 文件的节区表。"""
    pe_sig_off = struct.unpack_from('<I', data, 0x3C)[0]
    coff_off = pe_sig_off + 4
    num_sections = struct.unpack_from('<H', data, coff_off + 2)[0]
    opt_hdr_size = struct.unpack_from('<H', data, coff_off + 16)[0]
    section_off = coff_off + 20 + opt_hdr_size

    sections = []
    for i in range(num_sections):
        off = section_off + i * 40
        name = data[off:off + 8].rstrip(b'\x00').decode('ascii', errors='replace')
        raw_size = struct.unpack_from('<I', data, off + 16)[0]
        raw_off = struct.unpack_from('<I', data, off + 20)[0]
        sections.append({'name': name, 'raw_offset': raw_off, 'raw_size': raw_size})
    return sections


def find_bun_section(sections: list[dict]) -> dict | None:
    for sec in sections:
        if sec['name'] == '.bun':
            return sec
    return None


def _clean_bun_filename(raw_path: str) -> str:
    basename = raw_path.rsplit('/', 1)[-1] if '/' in raw_path else raw_path
    name_match = re.match(r'^(.+?)-[a-z0-9]{8}(\.\w+)$', basename)
    if name_match:
        return name_match.group(1) + name_match.group(2)
    return basename


def _write_extracted_file(output_dir: Path, raw_path: str, content: bytes, overwrite: bool = True) -> list[str]:
    written: list[str] = []
    basename = raw_path.rsplit('/', 1)[-1] if '/' in raw_path else raw_path
    clean_name = _clean_bun_filename(raw_path)

    if raw_path.startswith(VIRTUAL_ROOT_PREFIX):
        virtual_path = output_dir / VIRTUAL_ROOT_DIR / basename
        virtual_path.parent.mkdir(parents=True, exist_ok=True)
        if overwrite or not virtual_path.exists():
            virtual_path.write_bytes(content)
        written.append(str(VIRTUAL_ROOT_DIR / basename))

    out_path = output_dir / clean_name
    if overwrite or not out_path.exists():
        out_path.write_bytes(content)
    written.append(clean_name)
    return written


def _iter_embedded_file_records(data: bytes, bun_sec: dict) -> list[tuple[str, bytes]]:
    bun_off = bun_sec['raw_offset']
    data_size = struct.unpack_from('<Q', data, bun_off)[0]
    data_start = bun_off + 8
    data_end = data_start + data_size

    needle = VIRTUAL_ROOT_PREFIX.encode("utf-8")
    starts: list[tuple[int, int, str]] = []
    pos = data_start
    while True:
        path_start = data.find(needle, pos, data_end)
        if path_start == -1:
            break
        pos = path_start + 1
        if path_start <= data_start or data[path_start - 1] != 0:
            continue
        path_end = data.find(b"\x00", path_start, min(path_start + 300, data_end))
        if path_end == -1:
            continue
        try:
            raw_path = data[path_start:path_end].decode("utf-8")
        except UnicodeDecodeError:
            continue
        starts.append((path_start, path_end, raw_path))

    records: list[tuple[str, bytes]] = []
    for index, (path_start, path_end, raw_path) in enumerate(starts):
        content_start = path_end + 1
        content_end = starts[index + 1][0] - 1 if index + 1 < len(starts) else data_end
        if content_start < content_end:
            records.append((raw_path, data[content_start:content_end]))
    return records


def rewrite_virtual_paths(output_dir: Path) -> bool:
    index_js = output_dir / "index.js"
    if not index_js.exists():
        return False
    text = index_js.read_text(encoding="utf-8", errors="ignore")
    virtual_root = (output_dir / VIRTUAL_ROOT_DIR).resolve().as_posix()
    updated = text.replace(VIRTUAL_ROOT_PREFIX, f"{virtual_root}/")
    if updated == text:
        return False
    index_js.write_text(updated, encoding="utf-8")
    return True


def ensure_runtime_resources(output_dir: Path, target: Path | None = None) -> list[str]:
    """补齐 JS bundle 运行时需要的 Bun 虚拟文件资源。"""
    target_path = (target or discover_target()).expanduser().resolve()
    if not target_path.exists():
        print_status("⚠️", f"无法补齐运行时资源，未找到 qodercli.exe: {target_path}")
        return []

    data = target_path.read_bytes()
    bun_sec = find_bun_section(parse_pe_sections(data))
    if bun_sec is None:
        print_status("⚠️", "无法补齐运行时资源，未找到 .bun 节区")
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for raw_path, content in _iter_embedded_file_records(data, bun_sec):
        basename = raw_path.rsplit('/', 1)[-1]
        if basename == "index.js":
            continue
        virtual_path = output_dir / VIRTUAL_ROOT_DIR / basename
        if virtual_path.exists():
            continue
        written.extend(_write_extracted_file(output_dir, raw_path, content, overwrite=False))

    if rewrite_virtual_paths(output_dir):
        written.append("index.js")
    return written


def extract_modules(data: bytes, bun_sec: dict, output_dir: Path) -> list[str]:
    """从 .bun 节区提取所有嵌入模块。

    .bun 节区布局：
    [8B size_header(u64 LE)]
    [data: entry_path\\0 + JS source + null padding + embedded files...]
    [module_table]
    [offsets_struct]
    [\\n---- Bun! ----\\n]
    [section padding to alignment]
    """
    bun_off = bun_sec['raw_offset']
    data_size = struct.unpack_from('<Q', data, bun_off)[0]
    data_start = bun_off + 8
    data_end = data_start + data_size

    # 定位 trailer
    trailer = b'\n---- Bun! ----\n'
    trailer_pos = data.rfind(trailer, data_start, data_end + 64)
    if trailer_pos == -1:
        print_status("❌", "未找到 Bun trailer")
        return []

    # 解析 offsets struct（trailer 前 32 字节）
    # 格式：[entry_module_off: u64] [modules_list_off: u32] [modules_list_len: u32]
    #        [padding: u32] [something: u64] [module_count: u32]
    ofs_raw = data[trailer_pos - 32 : trailer_pos]
    # 实际结构（从逆向分析验证）：最后 4 字节 = module_count
    module_count = struct.unpack_from('<I', ofs_raw, 28)[0]
    modules_list_off = struct.unpack_from('<I', ofs_raw, 8)[0]
    modules_list_len = struct.unpack_from('<I', ofs_raw, 12)[0]

    if module_count == 0 or module_count > 10000:
        print_status("❌", f"模块数异常: {module_count}")
        return []

    entry_size = modules_list_len // module_count
    print_status("📌", f"模块数: {module_count}, 每模块 {entry_size} 字节")

    # 读取模块表
    mod_table_start = data_start + modules_list_off
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted = []

    for i in range(module_count):
        entry_off = mod_table_start + i * entry_size
        # 每两个 entry 组成一对：偶数 = 数据，奇数 = 元数据/标志
        # 偶数 entry 前 16 字节: path_off(u32), path_len(u32), code_off(u32), code_len(u32)
        if i % 2 != 0:
            continue  # 跳过奇数条目（元数据/标志）

        path_off = struct.unpack_from('<I', data, entry_off)[0]
        path_len = struct.unpack_from('<I', data, entry_off + 4)[0]
        code_off = struct.unpack_from('<I', data, entry_off + 8)[0]
        code_len = struct.unpack_from('<I', data, entry_off + 12)[0]

        if path_len == 0 or path_len > 500 or code_len == 0:
            continue

        # 读取路径
        abs_path_off = data_start + path_off
        raw_path = data[abs_path_off : abs_path_off + path_len].decode('utf-8', errors='replace').rstrip('\x00')

        # 读取内容
        abs_code_off = data_start + code_off
        content = data[abs_code_off : abs_code_off + code_len]

        # 写入文件
        written = _write_extracted_file(output_dir, raw_path, content)
        clean_name = _clean_bun_filename(raw_path)
        extracted.extend(written)

        size_str = f"{code_len:,}" if code_len < 1024 * 1024 else f"{code_len / 1024 / 1024:.1f} MB"
        print_status("✅", f"  {clean_name} ({size_str})")

    embedded_records = _iter_embedded_file_records(data, bun_sec)
    extra_count = 0
    for raw_path, content in embedded_records:
        if raw_path.endswith("/index.js"):
            continue
        written = _write_extracted_file(output_dir, raw_path, content)
        extracted.extend(written)
        extra_count += 1

    if rewrite_virtual_paths(output_dir):
        print_status("✅", "  index.js (已重写 Bun 虚拟资源路径)")

    if extra_count:
        print_status("✅", f"  已补齐 Bun 虚拟资源 {extra_count} 个")

    return extracted


# ---------------------------------------------------------------------------
# 无感启动配置（shim）
# ---------------------------------------------------------------------------

def _get_ps_profile_paths() -> list[tuple[str, Path]]:
    """获取所有 PowerShell $PROFILE 路径（Windows PowerShell + PowerShell 7）。"""
    profiles: list[tuple[str, Path]] = []
    seen: set[str] = set()

    def add_profile(label: str, path: Path) -> None:
        expanded = path.expanduser()
        key = str(expanded).lower()
        if key not in seen:
            seen.add(key)
            profiles.append((label, expanded))

    shells = [
        ("Windows PowerShell", r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"),
        ("PowerShell 7", "pwsh.exe"),
    ]
    for label, exe in shells:
        try:
            result = subprocess.run(
                [exe, "-NoProfile", "-Command", "Write-Output $PROFILE"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                add_profile(label, Path(result.stdout.strip()))
        except Exception:
            pass

    # Some launched shells report a redirected Documents path that differs from
    # the interactive shell currently running this script. Also cover the
    # conventional current-user profile locations so qodercli resolves to the
    # shim after a normal terminal restart.
    homes: list[Path] = []
    for value in (os.environ.get("USERPROFILE"), os.environ.get("HOME"), str(Path.home())):
        if value:
            home = Path(value).expanduser()
            if home not in homes:
                homes.append(home)
    for home in homes:
        add_profile("PowerShell 7 current-user fallback", home / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1")
        add_profile("Windows PowerShell current-user fallback", home / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1")

    return profiles


def _get_bashrc_path() -> Path:
    return Path.home() / ".bashrc"


PS_SHIM = f"""\n{SHIM_MARKER}
{SHIM_VERSION_MARKER}
function qodercli {{
    $extractedJs = "$env:USERPROFILE\\.qoder\\extracted\\index.js"
    $bunExe = "$env:LOCALAPPDATA\\Kiro-Cli\\bun.exe"
    if ((Test-Path $extractedJs) -and (Test-Path $bunExe)) {{
        function ConvertFrom-QoderUtf8Mojibake([string]$text) {{
            if ([string]::IsNullOrEmpty($text)) {{
                return $text
            }}
            $bytes = [System.Collections.Generic.List[byte]]::new()
            foreach ($char in $text.ToCharArray()) {{
                $code = [int][char]$char
                if ($code -le 255) {{
                    $bytes.Add([byte]$code)
                }} else {{
                    $bytes.AddRange([System.Text.Encoding]::UTF8.GetBytes([string]$char))
                }}
            }}
            return [System.Text.Encoding]::UTF8.GetString($bytes.ToArray())
        }}

        $prevOutputEncoding = [Console]::OutputEncoding
        $prevInputEncoding = [Console]::InputEncoding
        $prevLang = $env:LANG
        $prevLcAll = $env:LC_ALL
        $prevPythonIoEncoding = $env:PYTHONIOENCODING
        $prevCodePage = $null
        $chcpOutput = & cmd /c chcp 2>$null
        if ($chcpOutput -match ':\\s*([0-9]+)') {{
            $prevCodePage = $Matches[1]
        }}
        $qoderExitCode = $null
        try {{
            chcp 65001 | Out-Null
            [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
            [Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
            $env:LANG = "en_US.UTF-8"
            $env:LC_ALL = "en_US.UTF-8"
            $env:PYTHONIOENCODING = "utf-8"
            $qoderArgs = @($args)
            $shouldDecodeHelpOutput = $false
            foreach ($arg in $qoderArgs) {{
                if (@("--help", "-h", "help", "--version", "-v", "version") -contains [string]$arg) {{
                    $shouldDecodeHelpOutput = $true
                    break
                }}
            }}
            if ($shouldDecodeHelpOutput) {{
                $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
                $startInfo.FileName = $bunExe
                $startInfo.UseShellExecute = $false
                $startInfo.RedirectStandardOutput = $true
                $startInfo.RedirectStandardError = $true
                $startInfo.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
                $startInfo.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)
                [void]$startInfo.ArgumentList.Add("run")
                [void]$startInfo.ArgumentList.Add($extractedJs)
                foreach ($arg in $qoderArgs) {{
                    [void]$startInfo.ArgumentList.Add([string]$arg)
                }}
                $process = [System.Diagnostics.Process]::Start($startInfo)
                $stdout = $process.StandardOutput.ReadToEnd()
                $stderr = $process.StandardError.ReadToEnd()
                $process.WaitForExit()
                $decodedStdout = ConvertFrom-QoderUtf8Mojibake $stdout
                if ($decodedStdout.Length -gt 0) {{
                    Write-Output -NoEnumerate $decodedStdout
                }}
                [Console]::Error.Write((ConvertFrom-QoderUtf8Mojibake $stderr))
                $qoderExitCode = $process.ExitCode
            }} else {{
                & $bunExe run $extractedJs @args
                $qoderExitCode = $LASTEXITCODE
            }}
        }} finally {{
            [Console]::OutputEncoding = $prevOutputEncoding
            [Console]::InputEncoding = $prevInputEncoding
            if ($null -eq $prevLang) {{ Remove-Item Env:LANG -ErrorAction SilentlyContinue }} else {{ $env:LANG = $prevLang }}
            if ($null -eq $prevLcAll) {{ Remove-Item Env:LC_ALL -ErrorAction SilentlyContinue }} else {{ $env:LC_ALL = $prevLcAll }}
            if ($null -eq $prevPythonIoEncoding) {{ Remove-Item Env:PYTHONIOENCODING -ErrorAction SilentlyContinue }} else {{ $env:PYTHONIOENCODING = $prevPythonIoEncoding }}
            if ($prevCodePage) {{
                chcp $prevCodePage | Out-Null
            }}
        }}
        if ($null -ne $qoderExitCode) {{
            $global:LASTEXITCODE = $qoderExitCode
        }}
    }} else {{
        & "$env:ProgramFiles\\nodejs\\node_modules\\@qoder-ai\\qodercli\\bin\\qodercli.exe" @args
    }}
}}
# Qoder CLI 汉化版 - 结束
"""

BASH_SHIM = f"""\n{SHIM_MARKER}
qodercli() {{
    local extracted="$USERPROFILE/.qoder/extracted/index.js"
    local bun_exe="$LOCALAPPDATA/Kiro-Cli/bun"
    if [ -f "$extracted" ] && [ -f "$bun_exe" ]; then
        "$bun_exe" run "$extracted" "$@"
    else
        command qodercli "$@"
    fi
}}
# Qoder CLI 汉化版 - 结束
"""


def _has_shim(content: str) -> bool:
    return SHIM_MARKER in content


def _remove_shim_block(content: str) -> str:
    """移除 SHIM_MARKER 到结束标记之间的内容。"""
    start_marker = SHIM_MARKER
    end_marker = "# Qoder CLI 汉化版 - 结束"
    lines = content.split('\n')
    result = []
    skipping = False
    for line in lines:
        if start_marker in line:
            skipping = True
            # 移除前面的空行
            while result and result[-1].strip() == '':
                result.pop()
            continue
        if skipping and end_marker in line:
            skipping = False
            continue
        if not skipping:
            result.append(line)
    return '\n'.join(result)


def _ensure_bun_exe() -> None:
    """确保 bun.exe 存在（Windows 需要 .exe 扩展名才能直接执行）。

    Kiro-Cli 自带的 bun 二进制无扩展名，Windows 会将其视为文档打开。
    通过硬链接（同卷无需额外空间）创建 bun.exe，回退到复制。
    """
    bun_src = Path(os.environ.get("LOCALAPPDATA", "")) / "Kiro-Cli" / "bun"
    bun_exe = bun_src.with_name("bun.exe")
    if not bun_src.exists():
        return
    if bun_exe.exists():
        return
    try:
        os.link(bun_src, bun_exe)
        print_status("✅", f"已创建硬链接: {bun_exe}")
    except OSError:
        import shutil
        shutil.copy2(bun_src, bun_exe)
        print_status("✅", f"已复制 bun → bun.exe: {bun_exe}")


def _is_shim_outdated(content: str) -> bool:
    """检查已安装的 shim 是否是旧版本。
    
    检测条件：
    - bun 路径缺少 .exe 扩展名（旧版）
    - 缺少 UTF-8 编码设置（第一版）
    - 缺少编码恢复逻辑（第二版）
    - 缺少输入编码、LC_ALL、try/finally 或当前版本标记（第三版）
    - 缺少 help/version 输出纠偏逻辑（第四版）
    
    文件中的 shim 内容含单反斜杠路径，如 Kiro-Cli\\bun"（Python: 'Kiro-Cli\\bun"'）。
    """
    if SHIM_MARKER not in content:
        return False
    old_bun = r'Kiro-Cli\bun"' in content and 'bun.exe' not in content
    missing_utf8 = 'OutputEncoding' not in content
    missing_input_encoding = 'InputEncoding' not in content
    missing_lc_all = 'LC_ALL' not in content
    missing_try_finally = 'try {' not in content or 'finally {' not in content
    missing_help_decode = 'ConvertFrom-QoderUtf8Mojibake' not in content or 'ProcessStartInfo' not in content
    missing_version = SHIM_VERSION_MARKER not in content
    return old_bun or missing_utf8 or missing_input_encoding or missing_lc_all or missing_try_finally or missing_help_decode or missing_version


def install_shim() -> None:
    """安装启动劫持到所有 PowerShell $PROFILE 和 ~/.bashrc。"""
    _ensure_bun_exe()
    installed = False

    # PowerShell $PROFILE（Windows PowerShell + PowerShell 7）
    ps_profiles = _get_ps_profile_paths()
    if not ps_profiles:
        print_status("⚠️", "未找到任何 PowerShell $PROFILE 路径")
    for label, ps_profile in ps_profiles:
        ps_profile.parent.mkdir(parents=True, exist_ok=True)
        existing = ps_profile.read_text(encoding='utf-8') if ps_profile.exists() else ""
        if _has_shim(existing):
            if _is_shim_outdated(existing):
                # 旧版 shim 使用无扩展名 bun 路径，自动升级
                cleaned = _remove_shim_block(existing)
                ps_profile.write_text(cleaned + PS_SHIM, encoding='utf-8')
                print_status("✅", f"已升级 {label} $PROFILE: {ps_profile}")
                installed = True
            else:
                print_status("⏭️", f"{label} $PROFILE 已配置: {ps_profile}")
        else:
            ps_profile.write_text(existing + PS_SHIM, encoding='utf-8')
            print_status("✅", f"已写入 {label} $PROFILE: {ps_profile}")
            installed = True

    # Git Bash ~/.bashrc
    bashrc = _get_bashrc_path()
    existing = bashrc.read_text(encoding='utf-8') if bashrc.exists() else ""
    if _has_shim(existing):
        print_status("⏭️", f"~/.bashrc 已配置: {bashrc}")
    else:
        bashrc.write_text(existing + BASH_SHIM, encoding='utf-8')
        print_status("✅", f"已写入 ~/.bashrc: {bashrc}")
        installed = True

    if installed:
        print_status("📌", "请重新打开终端窗口以使 qodercli 命令指向汉化版")


def uninstall_shim() -> None:
    """移除所有启动劫持配置。"""
    # PowerShell $PROFILE（Windows PowerShell + PowerShell 7）
    for label, ps_profile in _get_ps_profile_paths():
        if ps_profile.exists():
            content = ps_profile.read_text(encoding='utf-8')
            if _has_shim(content):
                cleaned = _remove_shim_block(content)
                ps_profile.write_text(cleaned, encoding='utf-8')
                print_status("✅", f"已从 {label} $PROFILE 移除: {ps_profile}")
            else:
                print_status("⏭️", f"{label} $PROFILE 无需清理")

    # Git Bash ~/.bashrc
    bashrc = _get_bashrc_path()
    if bashrc.exists():
        content = bashrc.read_text(encoding='utf-8')
        if _has_shim(content):
            cleaned = _remove_shim_block(content)
            bashrc.write_text(cleaned, encoding='utf-8')
            print_status("✅", f"已从 ~/.bashrc 移除: {bashrc}")
        else:
            print_status("⏭️", f"~/.bashrc 无需清理")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从 qodercli.exe 提取 JS bundle 并配置无感启动。"
    )
    parser.add_argument("--target", type=Path, help="qodercli.exe 路径；不传时自动发现")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"输出目录（默认 {DEFAULT_OUTPUT}）")
    parser.add_argument("--no-shim", action="store_true",
                        help="只提取，不配置启动劫持")
    parser.add_argument("--uninstall-shim", action="store_true",
                        help="移除启动劫持配置")
    return parser.parse_args()


def main() -> int:
    init_terminal()
    args = parse_args()

    if args.uninstall_shim:
        uninstall_shim()
        return 0

    target = (args.target or discover_target()).expanduser().resolve()
    print_status("📌", f"目标文件: {target}")

    if not target.exists():
        print_status("❌", f"目标文件不存在: {target}")
        return 1

    print_status("📌", f"文件大小: {target.stat().st_size / 1024 / 1024:.1f} MB")

    # 读取 PE 头（只需前 4KB）+ .bun 节区
    data = target.read_bytes()
    sections = parse_pe_sections(data)

    bun_sec = find_bun_section(sections)
    if bun_sec is None:
        print_status("❌", "未找到 .bun 节区，此文件可能不是 Bun standalone 可执行文件")
        return 1

    print_status("📌", f".bun 节区: offset=0x{bun_sec['raw_offset']:X}, size={bun_sec['raw_size'] / 1024 / 1024:.1f} MB")

    output_dir = args.output.expanduser().resolve()
    print_status("📌", f"输出目录: {output_dir}")

    extracted = extract_modules(data, bun_sec, output_dir)
    if not extracted:
        print_status("❌", "未提取到任何模块")
        return 1

    print_status("🎉", f"成功提取 {len(extracted)} 个文件到 {output_dir}")

    # 配置无感启动
    if not args.no_shim:
        print_status("📌", "配置无感启动...")
        install_shim()

    return 0


if __name__ == "__main__":
    sys.exit(main())
