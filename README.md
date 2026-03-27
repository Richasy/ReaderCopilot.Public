<p align="center">
  <img src="assets/logo.svg" width="80" alt="Rodel Reader logo" />
</p>

<div align="center">

# Rodel Reader

> [!IMPORTANT]
> Rodel Reader has entered the next development phase. The current version is no longer maintained. After the code was frozen, we made the package publicly available for users who prefer the legacy experience. For the new version, please visit the new repository: [Rodel.Reader.Public](https://github.com/Richasy/Rodel.Reader.Public)

`Rodel Reader` can read e-books, and support RSS / Podcasts.

[![Chinese](https://img.shields.io/badge/中文-README-blue)](./README.zh-CN.md)

</div>
<p align="center">
<a href="#overview">Overview</a> &nbsp;&bull;&nbsp;
<a href="#platform">Platform</a> &nbsp;&bull;&nbsp;
<a href="#download--install">Download & Install</a> &nbsp;&bull;&nbsp;
<a href="#usage">Usage</a>
</p>

## Overview

[Rodel Reader](https://apps.microsoft.com/detail/9PFZCKRHW0BC) is a Windows desktop reading tool that provides you with a high-quality reading experience through a user interface that adheres to Fluent Design.

It has three main functional sections:

- 📚 **E-books**
  Supports various e-book formats such as `TXT` / `EPUB` / `AZW3` / `MOBI` / `CBZ` / `FB2` / `PDF` / `ZIP(comic)`, meeting common reading needs.<br/><br/>
- 📰 **RSS**
  Supports services like `Local` / `Feedbin` / `Google Reader (API)` / `Inoreader` / `Miniflux` / `NewsBlur`.<br/><br/>
- 📻 **Podcasts**
  You can view `iTunes` podcast lists within the app and subscribe to `Bilibili` accounts, converting Bilibili videos to podcast subscriptions.<br/><br/>

Rodel Reader strives to provide out-of-the-box functionality, but some services may require configuration on your part.

- 🤖 **AI Services**
  Rodel Reader can further enhance your reading efficiency through AI, supporting nearly 20 local or online AI dialogue interfaces, including `OpenAI` and `Ollama`. However, you need to provide the corresponding configuration information. For specific configuration methods, please refer to [Rodel Agent | Dialogue Service Configuration](https://agent.richasy.net/en/chat-config)<br/><br/>
- 🌏 **Translation Services**
  Rodel Reader supports text translation and full-text translation (RSS only). If you need to use these functions, you need to provide the corresponding translation service configuration. For specific configuration information, please refer to [Rodel Agent | Machine Translation Service Configuration](https://agent.richasy.net/en/translate-config)<br/><br/>
- 🎙️ **Text-to-Speech**
  Rodel Reader integrates local speech generation services and Edge speech generation services, but also provides additional text-to-speech service configurations. You can refer to [Rodel Agent | Text-to-Speech Service Configuration](https://agent.richasy.net/en/tts-config)<br/><br/>

## Platform

Only available for Windows desktop environments.

Minimum supported version is Windows 10 ver.19041.

## Download & Install

The app is distributed as a sideloaded Windows App SDK (MSIX) package. Follow the steps below to install.

### 1. Download the package

Go to the [Releases](https://github.com/Richasy/ReaderCopilot.Public/releases) page and download the zip file that matches your CPU architecture:

| Architecture | File |
|---|---|
| Intel / AMD (most PCs) | `ReaderCopilot_2.2512.1.0_x64.zip` |
| ARM64 (e.g. Surface Pro X, Snapdragon laptops) | `ReaderCopilot_2.2512.1.0_arm64.zip` |

> **Not sure which to choose?** Press `Win + I` → System → About, and check **System type**. If it says "x64-based processor", download the x64 version; if it says "ARM-based processor", download the ARM64 version.

### 2. Extract the zip

Right-click the downloaded zip file and select **Extract All...**, then choose a location (e.g. your Desktop).

After extraction, you should see three files:

| File | Description |
|---|---|
| `ReaderCopilot.UI_2.2512.1.0_x64.cer` (or arm64) | Security certificate |
| `ReaderCopilot.UI_2.2512.1.0_x64.msix` (or arm64) | App package |
| `Microsoft.WindowsAppRuntime.1.8.msix` | Windows App SDK runtime (required dependency) |

### 3. Install the certificate

You need to trust the signing certificate before installing the app.

1. Double-click the `.cer` file.
2. Click **Install Certificate...**.
3. Select **Local Machine**, then click **Next** (you may be prompted with a UAC dialog — click **Yes**).
4. Select **Place all certificates in the following store**, then click **Browse...**.
5. Choose **Trusted Root Certification Authorities**, click **OK**, then **Next**, then **Finish**.
6. You should see a message saying the import was successful.

### 4. Install the Windows App SDK runtime

Double-click `Microsoft.WindowsAppRuntime.1.8.msix` and follow the prompts to install it. If it is already installed on your system, you can skip this step.

### 5. Install the app

Double-click the `.msix` file (e.g. `ReaderCopilot.UI_2.2512.1.0_x64.msix`). An installation dialog will appear — click **Install**. Once finished, the app will launch automatically.

## Usage

For detailed usage instructions, please visit [Rodel Reader Document](https://reader.richasy.net/en/)

## Screenshot

![Screenshot](./assets/screenshot.png)
