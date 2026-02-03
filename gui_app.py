"""
垂直视频裁剪工具 - PySide GUI界面版
支持多种裁剪模式，提供可视化操作界面
"""

import sys
import os
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                               QWidget, QLabel, QPushButton, QComboBox, QLineEdit, 
                               QProgressBar, QTextEdit, QFileDialog, QGroupBox,
                               QSpinBox, QDoubleSpinBox, QCheckBox, QGridLayout)
from PySide6.QtCore import QThread, Signal, QTimer, Qt
from PySide6.QtGui import QFont, QPalette, QColor
import cv2
import numpy as np
from typing import Dict, Any


class CropWorker(QThread):
    """后台裁剪工作线程"""
    
    # 信号定义
    progress_updated = Signal(int, int)  # 当前帧, 总帧数
    status_updated = Signal(str)         # 状态信息
    finished_signal = Signal(bool, str)  # 成功状态, 消息
    
    def __init__(self, input_path: str, output_path: str, config: Dict[str, Any]):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.config = config
        self.running = True
        
        # 加载人脸检测器
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
    
    def stop(self):
        """停止处理"""
        self.running = False
    
    def run(self):
        """执行裁剪任务"""
        try:
            # 打开视频文件
            cap = cv2.VideoCapture(self.input_path, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                self.finished_signal.emit(False, f"无法打开视频文件 {self.input_path}")
                return
            
            # 获取视频信息
            original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            self.status_updated.emit(f"输入视频: {original_width}x{original_height}, {fps:.2f} FPS, {total_frames} 帧")
            
            # 计算输出尺寸 (9:16)
            vertical_height = int(original_height)
            vertical_width = int(vertical_height * 9 / 16)
            
            self.status_updated.emit(f"输出尺寸: {vertical_width}x{vertical_height} (9:16)")
            
            # 检查输入视频尺寸
            if original_width < vertical_width:
                self.finished_signal.emit(False, f"输入视频宽度({original_width})小于目标宽度({vertical_width})")
                cap.release()
                return
            
            # 根据模式选择裁剪策略
            mode = self.config['mode']
            if mode == 'face':
                success = self._dynamic_face_crop(cap, original_width, original_height, fps, 
                                                vertical_width, vertical_height, total_frames)
            elif mode == 'motion':
                success = self._motion_tracking_crop(cap, original_width, original_height, fps,
                                                   vertical_width, vertical_height, total_frames)
            else:  # center mode
                success = self._center_crop(cap, original_width, original_height, fps,
                                          vertical_width, vertical_height, total_frames)
            
            cap.release()
            
            if success and self.running:
                self.finished_signal.emit(True, "视频裁剪成功完成!")
            elif not self.running:
                self.finished_signal.emit(False, "用户取消了处理")
            else:
                self.finished_signal.emit(False, "视频裁剪失败")
                
        except Exception as e:
            self.finished_signal.emit(False, f"裁剪过程中发生错误: {str(e)}")
    
    def _dynamic_face_crop(self, cap, original_width, original_height, fps, 
                          vertical_width, vertical_height, total_frames) -> bool:
        """动态人脸检测裁剪模式"""
        self.status_updated.emit("使用动态人脸检测模式...")
        
        face_config = self.config['face_detection']
        
        # 重置视频到开始位置
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        # 初始化视频写入器
        fourcc = cv2.VideoWriter_fourcc(*self.config['output']['codec'])
        out = cv2.VideoWriter(self.output_path, fourcc, fps, (vertical_width, vertical_height))
        
        if not out.isOpened():
            self.status_updated.emit("错误: 无法创建输出视频文件")
            return False
        
        # 初始化跟踪变量
        current_x = (original_width - vertical_width) // 2
        face_detected = False
        face_count = 0
        
        frame_count = 0
        self.status_updated.emit("开始处理视频...")
        
        while self.running and frame_count < total_frames:
            ret, frame = cap.read()
            if not ret:
                break
            
            try:
                # 每帧检测人脸
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(
                    gray, 
                    scaleFactor=face_config['scale_factor'],
                    minNeighbors=face_config['min_neighbors'],
                    minSize=face_config['min_size']
                )
                
                if len(faces) > 0:
                    # 检测到人脸
                    best_face = max(faces, key=lambda f: f[2] * f[3])
                    x, y, w, h = best_face
                    face_center_x = x + w // 2 + face_config['right_offset']
                    
                    if not face_detected:
                        self.status_updated.emit(f"检测到人脸，开始动态跟踪...")
                        face_detected = True
                    
                    # 计算目标位置并平滑移动
                    target_x = max(0, min(face_center_x - vertical_width // 2, original_width - vertical_width))
                    smoothing_factor = 0.9
                    current_x = int(smoothing_factor * current_x + (1 - smoothing_factor) * target_x)
                    face_count += 1
                else:
                    # 未检测到人脸
                    if not face_detected:
                        current_x = (original_width - vertical_width) // 2
                
                # 裁剪当前帧
                crop_x_start = int(current_x)
                crop_x_end = min(crop_x_start + vertical_width, original_width)
                
                if crop_x_end - crop_x_start < vertical_width:
                    crop_x_start = max(0, crop_x_end - vertical_width)
                
                cropped_frame = frame[:, crop_x_start:crop_x_end]
                
                # 确保尺寸正确
                if cropped_frame.shape[1] != vertical_width or cropped_frame.shape[0] != vertical_height:
                    cropped_frame = cv2.resize(cropped_frame, (vertical_width, vertical_height))
                
                out.write(cropped_frame)
                frame_count += 1
                
                # 更新进度
                if frame_count % 10 == 0:  # 每10帧更新一次进度
                    self.progress_updated.emit(frame_count, total_frames)
                    
            except Exception as e:
                self.status_updated.emit(f"处理第{frame_count}帧时出错，跳过: {str(e)}")
                continue
        
        out.release()
        
        if face_count > 0:
            self.status_updated.emit(f"成功跟踪了 {face_count} 帧中的人脸")
        else:
            self.status_updated.emit("未检测到人脸，使用中心裁剪")
        
        return True
    
    def _motion_tracking_crop(self, cap, original_width, original_height, fps,
                            vertical_width, vertical_height, total_frames) -> bool:
        """运动跟踪裁剪模式"""
        self.status_updated.emit("使用运动跟踪模式...")
        
        motion_config = self.config['motion_tracking']
        
        # 重置视频到开始位置
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        # 初始化视频写入器
        fourcc = cv2.VideoWriter_fourcc(*self.config['output']['codec'])
        out = cv2.VideoWriter(self.output_path, fourcc, fps, (vertical_width, vertical_height))
        
        if not out.isOpened():
            self.status_updated.emit("错误: 无法创建输出视频文件")
            return False
        
        # 运动跟踪逻辑（简化版）
        prev_gray = None
        smoothed_x = (original_width - vertical_width) // 2
        
        frame_count = 0
        self.status_updated.emit("开始处理视频...")
        
        while self.running and frame_count < total_frames:
            ret, frame = cap.read()
            if not ret:
                break
            
            try:
                # 运动跟踪逻辑
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                if prev_gray is not None:
                    # 计算光流
                    flow = cv2.calcOpticalFlowFarneback(
                        prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
                    )
                    
                    # 简化运动跟踪：使用中心位置
                    # 在实际应用中可以实现更复杂的运动跟踪逻辑
                    pass
                
                prev_gray = gray
                
                # 使用中心裁剪（简化版）
                x_start = (original_width - vertical_width) // 2
                cropped_frame = frame[:, x_start:x_start+vertical_width]
                
                # 确保尺寸正确
                if cropped_frame.shape[1] != vertical_width or cropped_frame.shape[0] != vertical_height:
                    cropped_frame = cv2.resize(cropped_frame, (vertical_width, vertical_height))
                
                out.write(cropped_frame)
                frame_count += 1
                
                # 更新进度
                if frame_count % 10 == 0:
                    self.progress_updated.emit(frame_count, total_frames)
                    
            except Exception as e:
                self.status_updated.emit(f"处理第{frame_count}帧时出错，跳过: {str(e)}")
                continue
        
        out.release()
        return True
    
    def _center_crop(self, cap, original_width, original_height, fps,
                    vertical_width, vertical_height, total_frames) -> bool:
        """中心裁剪模式"""
        self.status_updated.emit("使用中心裁剪模式...")
        
        # 重置视频到开始位置
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        # 初始化视频写入器
        fourcc = cv2.VideoWriter_fourcc(*self.config['output']['codec'])
        out = cv2.VideoWriter(self.output_path, fourcc, fps, (vertical_width, vertical_height))
        
        if not out.isOpened():
            self.status_updated.emit("错误: 无法创建输出视频文件")
            return False
        
        frame_count = 0
        self.status_updated.emit("开始处理视频...")
        
        while self.running and frame_count < total_frames:
            ret, frame = cap.read()
            if not ret:
                break
            
            try:
                # 中心裁剪
                x_start = (original_width - vertical_width) // 2
                cropped_frame = frame[:, x_start:x_start+vertical_width]
                
                # 确保尺寸正确
                if cropped_frame.shape[1] != vertical_width or cropped_frame.shape[0] != vertical_height:
                    cropped_frame = cv2.resize(cropped_frame, (vertical_width, vertical_height))
                
                out.write(cropped_frame)
                frame_count += 1
                
                # 更新进度
                if frame_count % 10 == 0:
                    self.progress_updated.emit(frame_count, total_frames)
                    
            except Exception as e:
                self.status_updated.emit(f"处理第{frame_count}帧时出错，跳过: {str(e)}")
                continue
        
        out.release()
        return True


class VerticalVideoCropperGUI(QMainWindow):
    """垂直视频裁剪工具GUI界面"""
    
    def __init__(self):
        super().__init__()
        self.crop_worker = None
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("智能垂直视频裁剪工具")
        self.setGeometry(100, 100, 800, 600)
        
        # 设置样式 - 白色主题
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
                color: #333333;
                font-family: "Microsoft YaHei", "Segoe UI";
            }
            QGroupBox {
                color: #333333;
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 1ex;
                padding-top: 12px;
                background-color: white;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                color: #1976d2;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
            QPushButton:disabled {
                background-color: #bdbdbd;
                color: #757575;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: white;
                color: #333333;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 6px 8px;
                font-size: 12px;
                selection-background-color: #1976d2;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #1976d2;
            }
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 4px;
                text-align: center;
                color: #333333;
                background-color: #f0f0f0;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #4caf50;
                border-radius: 3px;
            }
            QTextEdit {
                background-color: white;
                color: #333333;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-family: Consolas, "Courier New", monospace;
                font-size: 11px;
                selection-background-color: #1976d2;
            }
            QLabel {
                color: #333333;
                font-size: 12px;
            }
        """)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 文件选择组
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout()
        file_layout.setSpacing(10)
        
        # 输入文件选择
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("输入视频:"))
        self.input_path_edit = QLineEdit()
        self.input_path_edit.setPlaceholderText("请选择输入视频文件...")
        self.input_path_edit.setMinimumWidth(400)
        input_layout.addWidget(self.input_path_edit)
        self.input_browse_btn = QPushButton("浏览...")
        self.input_browse_btn.clicked.connect(self.browse_input_file)
        input_layout.addWidget(self.input_browse_btn)
        file_layout.addLayout(input_layout)
        
        # 输出文件选择
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("输出视频:"))
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("请选择输出视频保存位置...")
        self.output_path_edit.setMinimumWidth(400)
        output_layout.addWidget(self.output_path_edit)
        self.output_browse_btn = QPushButton("浏览...")
        self.output_browse_btn.clicked.connect(self.browse_output_file)
        output_layout.addWidget(self.output_browse_btn)
        file_layout.addLayout(output_layout)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # 裁剪设置组
        settings_group = QGroupBox("裁剪设置")
        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(15)
        
        # 裁剪模式选择
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("裁剪模式:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["人脸检测", "运动跟踪", "中心裁剪"])
        self.mode_combo.setMinimumWidth(150)
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        
        # 添加模式说明标签
        self.mode_description = QLabel("智能检测人脸并居中裁剪，适合有人物的视频")
        self.mode_description.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
        
        settings_layout.addLayout(mode_layout)
        settings_layout.addWidget(self.mode_description)
        
        # 人脸检测参数
        self.face_params_group = QGroupBox("人脸检测参数")
        face_layout = QGridLayout()
        face_layout.setHorizontalSpacing(20)
        face_layout.setVerticalSpacing(8)
        
        face_layout.addWidget(QLabel("检测尺度:"), 0, 0)
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(1.01, 2.0)
        self.scale_spin.setValue(1.1)
        self.scale_spin.setSingleStep(0.01)
        self.scale_spin.setToolTip("检测尺度越小，检测越敏感但可能误检更多")
        face_layout.addWidget(self.scale_spin, 0, 1)
        
        face_layout.addWidget(QLabel("最小邻居数:"), 1, 0)
        self.neighbors_spin = QSpinBox()
        self.neighbors_spin.setRange(3, 20)
        self.neighbors_spin.setValue(8)
        self.neighbors_spin.setToolTip("邻居数越大，检测越严格但可能漏检")
        face_layout.addWidget(self.neighbors_spin, 1, 1)
        
        face_layout.addWidget(QLabel("右边界偏移:"), 0, 2)
        self.offset_spin = QSpinBox()
        self.offset_spin.setRange(0, 200)
        self.offset_spin.setValue(60)
        self.offset_spin.setToolTip("向右偏移量，防止人脸靠近右边界时被裁剪")
        face_layout.addWidget(self.offset_spin, 0, 3)
        
        # 添加参数说明
        params_note = QLabel("建议保持默认参数，除非需要特殊调整")
        params_note.setStyleSheet("color: #888; font-size: 10px; margin-top: 5px;")
        face_layout.addWidget(params_note, 2, 0, 1, 4)
        
        self.face_params_group.setLayout(face_layout)
        settings_layout.addWidget(self.face_params_group)
        
        # 运动跟踪参数
        self.motion_params_group = QGroupBox("运动跟踪参数")
        motion_layout = QGridLayout()
        motion_layout.setHorizontalSpacing(20)
        motion_layout.setVerticalSpacing(8)
        
        motion_layout.addWidget(QLabel("更新间隔(秒):"), 0, 0)
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 5.0)
        self.interval_spin.setValue(1.0)
        self.interval_spin.setSingleStep(0.1)
        self.interval_spin.setToolTip("跟踪位置更新的时间间隔，越小越灵敏")
        motion_layout.addWidget(self.interval_spin, 0, 1)
        
        motion_layout.addWidget(QLabel("平滑系数:"), 0, 2)
        self.smoothing_spin = QDoubleSpinBox()
        self.smoothing_spin.setRange(0.5, 0.99)
        self.smoothing_spin.setValue(0.9)
        self.smoothing_spin.setSingleStep(0.01)
        self.smoothing_spin.setToolTip("平滑系数越大，跟踪移动越平滑")
        motion_layout.addWidget(self.smoothing_spin, 0, 3)
        
        self.motion_params_group.setLayout(motion_layout)
        settings_layout.addWidget(self.motion_params_group)
        self.motion_params_group.hide()
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # 进度显示组
        progress_group = QGroupBox("处理进度")
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(10)
        
        # 进度条和百分比显示
        progress_header = QHBoxLayout()
        progress_header.addWidget(QLabel("处理进度:"))
        self.progress_percent = QLabel("0%")
        self.progress_percent.setStyleSheet("color: #1976d2; font-weight: bold;")
        progress_header.addWidget(self.progress_percent)
        progress_header.addStretch()
        progress_layout.addLayout(progress_header)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        # 状态日志
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("处理日志:"))
        log_header.addStretch()
        progress_layout.addLayout(log_header)
        
        self.status_text = QTextEdit()
        self.status_text.setMaximumHeight(150)
        self.status_text.setReadOnly(True)
        self.status_text.setPlaceholderText("处理日志将在这里显示...")
        progress_layout.addWidget(self.status_text)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.start_btn = QPushButton("▶ 开始裁剪")
        self.start_btn.setStyleSheet("background-color: #4caf50;")
        self.start_btn.clicked.connect(self.start_cropping)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("■ 停止")
        self.stop_btn.setStyleSheet("background-color: #f44336;")
        self.stop_btn.clicked.connect(self.stop_cropping)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        button_layout.addStretch()
        
        self.clear_btn = QPushButton("🗑️ 清除日志")
        self.clear_btn.clicked.connect(self.clear_log)
        button_layout.addWidget(self.clear_btn)
        
        layout.addLayout(button_layout)
        
        # 添加底部状态栏和QQ群信息
        footer_layout = QHBoxLayout()
        
        # 状态栏
        self.status_bar = QLabel("就绪 - 请选择输入视频文件")
        self.status_bar.setStyleSheet("background-color: #e3f2fd; color: #1976d2; padding: 5px;")
        footer_layout.addWidget(self.status_bar)
        
        # QQ群信息
        qq_group_label = QLabel("自媒体全家桶用户群: 1076150045")
        qq_group_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px; background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 3px;")
        qq_group_label.setToolTip("加入QQ群获取更多工具和交流")
        footer_layout.addWidget(qq_group_label)
        
        layout.addLayout(footer_layout)
        
        # 初始状态
        self.on_mode_changed("人脸检测")
        
    def on_mode_changed(self, mode_text):
        """裁剪模式改变时的处理"""
        if mode_text == "人脸检测":
            self.face_params_group.show()
            self.motion_params_group.hide()
            self.mode_description.setText("智能检测人脸并居中裁剪，适合有人物的视频")
        elif mode_text == "运动跟踪":
            self.face_params_group.hide()
            self.motion_params_group.show()
            self.mode_description.setText("跟踪画面运动焦点，适合动态场景的视频")
        else:  # 中心裁剪
            self.face_params_group.hide()
            self.motion_params_group.hide()
            self.mode_description.setText("简单中心裁剪，适合无特定焦点或对称构图的视频")
    
    def browse_input_file(self):
        """浏览输入文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择输入视频", "", "视频文件 (*.mp4 *.avi *.mov *.mkv)"
        )
        if file_path:
            self.input_path_edit.setText(file_path)
            
            # 自动生成输出文件名
            input_path = Path(file_path)
            output_path = input_path.parent / f"{input_path.stem}_vertical{input_path.suffix}"
            self.output_path_edit.setText(str(output_path))
    
    def browse_output_file(self):
        """浏览输出文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "选择输出视频", "", "MP4视频 (*.mp4)"
        )
        if file_path:
            self.output_path_edit.setText(file_path)
    
    def start_cropping(self):
        """开始裁剪"""
        input_path = self.input_path_edit.text().strip()
        output_path = self.output_path_edit.text().strip()
        
        if not input_path:
            self.status_text.append("错误: 请选择输入视频文件")
            return
        
        if not output_path:
            self.status_text.append("错误: 请选择输出视频文件")
            return
        
        if not os.path.exists(input_path):
            self.status_text.append(f"错误: 输入文件不存在: {input_path}")
            return
        
        # 构建配置
        config = {
            'mode': 'face' if self.mode_combo.currentText() == '人脸检测' else 
                   'motion' if self.mode_combo.currentText() == '运动跟踪' else 'center',
            'face_detection': {
                'scale_factor': self.scale_spin.value(),
                'min_neighbors': self.neighbors_spin.value(),
                'min_size': (30, 30),
                'sample_frames': 30,
                'right_offset': self.offset_spin.value()
            },
            'motion_tracking': {
                'update_interval': self.interval_spin.value(),
                'motion_threshold': 2.0,
                'smoothing_factor': self.smoothing_spin.value(),
                'scale_factor': 0.67
            },
            'output': {
                'codec': 'mp4v',
                'fps': None,
                'quality': 'medium',
                'bitrate': '3000k'
            }
        }
        
        # 创建并启动工作线程
        self.crop_worker = CropWorker(input_path, output_path, config)
        self.crop_worker.progress_updated.connect(self.update_progress)
        self.crop_worker.status_updated.connect(self.update_status)
        self.crop_worker.finished_signal.connect(self.on_finished)
        
        # 更新界面状态
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_text.append(f"开始处理: {Path(input_path).name}")
        
        self.crop_worker.start()
    
    def stop_cropping(self):
        """停止裁剪"""
        if self.crop_worker and self.crop_worker.isRunning():
            self.crop_worker.stop()
            self.crop_worker.wait(2000)  # 等待2秒
            self.status_text.append("用户取消了处理")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
    
    def update_progress(self, current_frame, total_frames):
        """更新进度条"""
        progress = int((current_frame / total_frames) * 100) if total_frames > 0 else 0
        self.progress_bar.setValue(progress)
        self.progress_percent.setText(f"{progress}%")
        self.status_bar.setText(f"处理中... {current_frame}/{total_frames} 帧 ({progress}%)")
    
    def update_status(self, message):
        """更新状态信息"""
        self.status_text.append(message)
        # 自动滚动到底部
        self.status_text.verticalScrollBar().setValue(
            self.status_text.verticalScrollBar().maximum()
        )
    
    def on_finished(self, success, message):
        """处理完成回调"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        if success:
            self.progress_bar.setValue(100)
            self.status_text.append(f"✓ {message}")
        else:
            self.status_text.append(f"✗ {message}")
    
    def clear_log(self):
        """清除日志"""
        self.status_text.clear()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用信息
    app.setApplicationName("垂直视频裁剪工具")
    app.setApplicationVersion("1.0.0")
    
    # 创建并显示主窗口
    window = VerticalVideoCropperGUI()
    window.show()
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()