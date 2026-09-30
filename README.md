# world.execute(me); —ascii

![world.execute(me);](docs/images/mv-cover.png)

Mili《world.execute(me);》的字符动画。支持中英字幕、原曲同步播放和终端字符动画。

> 本仓库是 <https://github.com/yym8224961/world.execute-me-ascii> 的 fork，在原项目之上增加了 **Windows 支持**。macOS 部分与上游一致。

## Windows 单文件运行（推荐）

从本仓库的 **Releases** 下载 `world-execute-mv-windows.zip` 并解压，双击 `运行单文件.bat`，或在 Windows Terminal 中进入解压目录运行：

```powershell
py -3 world-execute-mv-win.pyz
```

音乐、动画、字幕、频谱数据同样内嵌在 `world-execute-mv-win.pyz` 内，运行全程不联网，也不需要另外指定 MP3。

需要 **Windows 10 或更新版本、Python 3.9 或更新版本（只用标准库）、PowerShell 5.1**（系统自带，无需安装）。按空格开始。推荐全屏，终端至少 64 列 × 24 行。

```powershell
# 从 2:38.7 开始直接播放
py -3 world-execute-mv-win.pyz --start 158.7 --autoplay
```

Windows 版的按键与 macOS 版完全相同，见下方「操作」表（其中 `+` / `-` 调音量，上游文档漏记，此处一并补上）。

## Windows 版改了什么

上游在 Windows 上无法运行，原因有三处（都在 release 包里）：官方 pyz 的入口脚本判断 `sys.platform != 'darwin'` 就直接退出；`player.py` 使用 `termios` / `tty` / `select` / `/dev/tty` / `signal.SIGHUP`，Windows 的 Python 标准库没有这些；音频时钟是 Swift 编译的 Mach-O universal binary，Windows 不能执行。渲染层 `scenes.py` 只 import `math`，完全可移植，因此没有改动。

Windows 分支的处理：

| 面 | Windows 实现 |
| --- | --- |
| 音频时钟 | `audio-clock-win.ps1`，用 WPF `System.Windows.Media.MediaPlayer`（底层是 Media Foundation），由 Python 以 PowerShell 子进程启动，说与 Swift 版同一套 stdin/stdout 行协议（`play`/`pause`/`seek`/`volume`/`quit` ↔ 每 1/60 秒一行 JSON） |
| 按键输入 | `winkeys.py`：`msvcrt.kbhit()` / `getwch()`，把方向键的 `0x00 K` / `0x00 M` 前缀翻译成 `Esc [ D` / `Esc [ C`，上游的按键分发循环因此不必改动 |
| 终端尺寸 | `os.get_terminal_size` 失败时退回 `shutil.get_terminal_size((100, 36))` |
| 信号 | `signal.SIGHUP` 在 Windows 上不存在，改为存在才注册 |
| 文本编码 | 读歌词与配置时显式 `encoding='utf-8'`（Windows 默认 cp936，读中文会崩）；`stdout` 钉在 UTF-8 |

`player.py` 里平台相关的点都分成 `if POSIX:` / `else:` 两支：macOS 走的仍是上游那套调用（`termios`、`/dev/tty`、`select`、Mach-O `audio-clock`），只有一句提示文案去掉了「macOS」字样。另外两处对两支同时生效——歌词与配置改为显式按 UTF-8 读取（macOS 默认也是 UTF-8，行为不变），以及取不到终端尺寸时的兜底（正常终端里不会触发）。

关于音频后端的选型：Windows 的 MCI（`mciSendStringW`）在 64 位进程里没有可用的 MP3 解码器——`mpegvideo` 驱动只注册在 `MCI32` 下，`mciqtz32.dll` 是 32 位组件，64 位调用返回错误 277；`waveaudio` 只处理 WAV。所以走 WPF MediaPlayer。

实测（Windows 11 26200，以下数字都是在打包产物 `dist/world-execute-mv-win.pyz` 与仓库源码上重跑的）：

| 项 | 结果 |
| --- | --- |
| 端到端实播 | 单文件包从 100 秒跑 20 秒音频，三次运行分别 481 / 469 / 463 帧（目标 480 帧，即 23.1–24.0 fps），最慢单帧渲染 115–116 ms，退出码 0，stderr 为空；源码 `py -3 player.py` 从 158.7 秒跑 11.3 秒：275 帧，退出码 0，stderr 为空 |
| 音画同步 | 音频时间是主时钟，慢帧只丢帧不散拍，`--report` 无「时钟停止更新」告警 |
| 时钟精度 | 走 3.005 秒墙钟，音频报 2.995 秒（-0.3%）；`seek 158.7` 报 158.700（误差 0）；暂停 1 秒位置不动（161.900→161.900） |
| 全时间轴渲染 | 0→211.9 秒每 0.25 秒一帧 × 三种终端尺寸（120×40 / 70×26 / 64×24）共 2541 帧，0 次异常 |
| 启动器 | `运行单文件.bat` 在 pyz 与 bat 同级、以及 bat 在仓库根（回落到 `dist/`）两种布局下都能定位到包 |
| 单元测试 | `tests/test_win_bundle.py` 7 项通过（音频时钟实听那项需 `WMV_ACCEPT_AUDIO=1`）；`tests/test_bundle.py` 在 Windows 上跳过 3 项 |

两处已知差异：WPF 报出的歌曲总时长是 211.984 秒，macOS AVFoundation 报 211.907 秒，差 0.077 秒，只影响结尾判定的一两个帧；全片 211.9 秒的连续实播、以及传统控制台下的配色没有实测。上面的帧率是在 stdout 重定向到文件、窗口隐藏的条件下测的，真实终端里的帧率没有单独计时。

## 单文件运行（macOS，上游）

从本仓库的 **Releases** 下载 `world-execute-mv-macos.zip` 并解压。音乐、动画、字幕、频谱数据和音频播放组件已经内嵌在 `world-execute-mv.pyz` 内，无需另外下载或指定 MP3。

需要 **macOS 12 或更新版本、Python 3.9 或更新版本**。音频组件同时包含 Apple Silicon 和 Intel 架构。终端播放器自身只使用 Python 标准库。

在 macOS「终端」中进入解压目录运行：

```sh
python3 world-execute-mv.pyz
```

也可双击 `运行单文件.command`，在系统终端中播放。按空格开始。推荐全屏，终端至少 64 列 × 24 行，128 列 × 44 行及以上效果更好。

```sh
# 从 2:38.7 开始直接播放
python3 world-execute-mv.pyz --start 158.7 --autoplay
```

内嵌音乐是随程序封装的资源，不是加密或 DRM。播放时会解包到当前用户的临时目录，正常退出后清理；不会读取旧电脑 Downloads 中的文件。运行过程无需联网。

## 操作

| 按键 | 功能 |
| --- | --- |
| 空格 | 开始／暂停 |
| 左／右 | 后退／前进 5 秒 |
| R | 从头播放 |
| Q | 退出 |
| H | 显示全部帮助 |
| 1–5 | 跳转章节 |
| +／− | 音量 +5%／−5% |

画面使用 ANSI 转义序列、框字符与 256 色（`ESC[38;5;n`）。macOS 版建议在「终端」中运行；Windows 版建议在 Windows Terminal 中运行，传统控制台（conhost）的显示效果没有实测。

## 从源码运行

仓库不保存音频文件。从源码运行或重新打包前，请将自己的音频放到本地 `media/song.mp3`。使用 Release 播放包无需此步骤。

Windows 下放到音频后直接运行即可，不需要编译任何组件：

```powershell
py -3 player.py
```

macOS 首次构建音频组件需要 Apple Command Line Tools（含 Swift 编译器）：

```sh
xcode-select --install
```

然后执行：

```sh
./run.sh
```

启动脚本在缺少 `audio-clock` 时自动编译本机架构。双击 `播放MV.command` 可在 macOS 系统终端中运行源码版。

## 重新打包

macOS：

```sh
python3 tools/build_bundle.py
python3 tests/test_bundle.py
```

Windows：

```powershell
py -3 tools/build_bundle_win.py
py -3 tests/test_win_bundle.py
```

Windows 打包脚本要求 `media/song.mp3` 存在，音频只进包、不进仓库。`tests/test_bundle.py` 校验的是 macOS 包，在 Windows 上会跳过。

构建输出在 `dist/`：

- `world-execute-mv.pyz` / `world-execute-mv-win.pyz`：内嵌音乐的单文件播放器（macOS / Windows）。
- `world-execute-mv-macos.zip` / `world-execute-mv-windows.zip`：包含播放器、启动器、说明的分发包。
- `SHA256SUMS.txt`：下载校验值。

音频以系统音频时钟驱动画面；暂停、跳转时字幕与动画跟随音频时间。构建会在单文件包内记录各资源 SHA-256 以检查完整性；macOS 版另外生成 universal 音频组件。

## 收录范围

本仓库为项目归档，包含当前播放器、字幕、频谱和构建工具。音乐仅内嵌于 Release 播放包。

本 fork 的 Windows Release 包与上游的 macOS Release 包做法一致：把同一首 `media/song.mp3` 打进单文件播放器，仓库本身不含音频文件。

原曲与歌词：Mili《world.execute(me);》。本项目是个人创作与备份，未对原曲、歌词或其他第三方素材授予额外使用许可。
