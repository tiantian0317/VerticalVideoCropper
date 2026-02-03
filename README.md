# 智能垂直视频裁剪工具 (Vertical Video Cropper)

一个独立的智能工具，用于将横屏视频自动裁剪为9:16垂直格式，支持多种智能裁剪算法。

## 🖥️ Windows GUI 版本

为了方便使用，我们提供了图形界面版本，无需安装Python和依赖库。

### 下载与使用

1. **下载 GUI 版本**：
   - [VerticalVideoCropper.exe](https://github.com/tiantian0317/VerticalVideoCropper/releases/download/1.0/VerticalVideoCropper.exe)

2. **截图预览**：
   ![GUI 截图](https://github.com/tiantian0317/VerticalVideoCropper/blob/main/%E6%90%9C%E7%8B%97%E6%88%AA%E5%9B%BE20260203181512.png)

3. **使用说明**：
   - 直接双击运行 `VerticalVideoCropper.exe`
   - 选择输入视频文件
   - 配置裁剪参数（如裁剪模式、输出分辨率等）
   - 点击开始处理按钮
**📞 自媒体全家桶用户群：1076150045**

## 🎯 功能特性

- **多种裁剪模式**：人脸检测、运动跟踪、中心裁剪
- **智能算法**：自动选择最佳裁剪区域
- **高质量输出**：保持原视频质量
- **可配置参数**：灵活的裁剪参数调整
- **跨平台支持**：Windows/Linux/macOS

## 📦 安装依赖

### 方法一：使用pip安装（推荐）

```bash
# 安装核心依赖
pip install -r requirements.txt
```

### 方法二：手动安装

```bash
# 基础依赖
pip install opencv-python numpy moviepy

# 可选：进度条显示（开发时有用）
pip install tqdm
```

### 系统依赖

**Windows系统：**
- 无需额外安装，OpenCV自带预编译库

**Linux系统（Ubuntu/Debian）：**
```bash
# 安装系统依赖
sudo apt update
sudo apt install -y python3-pip ffmpeg libsm6 libxext6 libxrender-dev

# 对于更好的视频处理性能
sudo apt install -y libopencv-dev python3-opencv
```

**macOS系统：**
```bash
# 使用Homebrew安装
brew install ffmpeg
pip install opencv-python numpy moviepy
```

## 🚀 快速开始

### 基本使用

```bash
# 人脸检测模式（默认）
python vertical_video_cropper.py input.mp4 output.mp4

# 运动跟踪模式
python vertical_video_cropper.py input.mp4 output.mp4 --mode motion

# 中心裁剪模式
python vertical_video_cropper.py input.mp4 output.mp4 --mode center
```

### Python代码中使用

```python
from vertical_video_cropper import VerticalVideoCropper

# 默认配置（人脸检测模式）
cropper = VerticalVideoCropper()
success = cropper.crop_to_vertical('input.mp4', 'output.mp4')

# 自定义配置
config = {
    'mode': 'motion',
    'motion_tracking': {
        'update_interval': 0.5,
        'smoothing_factor': 0.95
    }
}

cropper = VerticalVideoCropper(config)
cropper.crop_to_vertical('input.mp4', 'output.mp4')
```

## ⚙️ 命令行参数

```bash
python vertical_video_cropper.py INPUT OUTPUT [OPTIONS]

参数说明：
  INPUT                  输入视频文件路径
  OUTPUT                 输出视频文件路径
  
选项：
  --mode {face,motion,center}  裁剪模式（默认: face）
  --scale-factor SCALE_FACTOR  运动跟踪缩放比例（默认: 0.67）
  --update-interval INTERVAL   运动跟踪更新间隔（秒）（默认: 1.0）
  --smoothing SMOOTHING        运动跟踪平滑系数（默认: 0.9）
  --help                      显示帮助信息
```

## 🔧 裁剪模式详解

### 1. 人脸检测模式 (`--mode face`)
- **原理**：检测视频前30帧中的人脸位置
- **适用场景**：人物访谈、vlog、演讲视频
- **优势**：静态裁剪，画面稳定
- **参数**：`sample_frames`, `right_offset`

### 2. 运动跟踪模式 (`--mode motion`)
- **原理**：使用光流算法跟踪画面运动焦点
- **适用场景**：屏幕录制、游戏录像、动态内容
- **优势**：智能跟随画面焦点移动
- **参数**：`update_interval`, `smoothing_factor`, `scale_factor`

### 3. 中心裁剪模式 (`--mode center`)
- **原理**：简单中心裁剪
- **适用场景**：对称构图、简单内容
- **优势**：处理速度快，无额外计算

## 📊 配置文件

工具支持通过字典配置参数：

```python
config = {
    'mode': 'face',  # 裁剪模式
    
    'face_detection': {
        'scale_factor': 1.1,      # 检测尺度
        'min_neighbors': 8,       # 最小邻居数
        'min_size': (30, 30),     # 最小人脸尺寸
        'sample_frames': 30,      # 采样帧数
        'right_offset': 60        # 右边界偏移
    },
    
    'motion_tracking': {
        'update_interval': 1.0,   # 更新间隔(秒)
        'motion_threshold': 2.0,  # 运动检测阈值
        'smoothing_factor': 0.9,  # 平滑系数
        'scale_factor': 0.67      # 缩放比例
    },
    
    'output': {
        'codec': 'mp4v',          # 输出编码
        'fps': None,              # 保持原FPS
        'quality': 'medium',      # 输出质量
        'bitrate': '3000k'        # 比特率
    }
}
```

## 🐛 故障排除

### 常见问题

**1. "无法打开视频文件"**
```bash
# 检查文件路径和权限
ls -la input.mp4
# 确保文件格式支持（MP4, AVI, MOV等）
```

**2. "OpenCV错误"**
```bash
# 重新安装OpenCV
pip uninstall opencv-python
pip install opencv-python
```

**3. "FFmpeg未找到"**
```bash
# 安装系统FFmpeg
# Ubuntu/Debian:
sudo apt install ffmpeg
# macOS:
brew install ffmpeg
# Windows: 下载FFmpeg并添加到PATH
```

**4. 内存不足**
```bash
# 对于大文件，考虑分批次处理
# 或使用更低分辨率的输入
```

### 性能优化

- **大文件处理**：使用更高配置的机器
- **实时处理**：调整`update_interval`参数
- **质量优先**：使用原视频分辨率，避免压缩

## 📁 项目结构

```
ver_vid_crop/
├── vertical_video_cropper.py  # 主程序文件
├── requirements.txt           # Python依赖
├── README.md                 # 说明文档
├── examples/                 # 示例目录
│   ├── basic_usage.py       # 基础使用示例
│   └── advanced_config.py   # 高级配置示例
└── tests/                   # 测试文件
    └── test_cropper.py      # 单元测试
```

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

### 开发环境设置

```bash
# 1. 克隆项目
git clone <repository-url>
cd ver_vid_crop

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# 3. 安装开发依赖
pip install -r requirements.txt
pip install pytest tqdm  # 开发工具

# 4. 运行测试
python -m pytest tests/
```

## 📄 许可证

MIT License - 详见LICENSE文件

## 🔗 相关项目

- [AI YouTube Shorts Generator](https://github.com/SamurAIGPT/AI-Youtube-Shorts-Generator) - 原项目
- [OpenCV](https://opencv.org/) - 计算机视觉库

- [MoviePy](https://zulko.github.io/moviepy/) - 视频编辑库
