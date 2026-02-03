#!/usr/bin/env python3
"""
智能垂直视频裁剪工具
将横屏视频自动裁剪为9:16垂直格式，支持多种智能裁剪模式

功能特性：
- 人脸检测模式：检测人脸并静态居中裁剪
- 运动跟踪模式：跟踪画面运动焦点，平滑移动裁剪区域
- 中心裁剪模式：简单中心裁剪
- 可配置参数：裁剪位置、缩放比例、跟踪速度等

使用示例：
    python vertical_video_cropper.py input.mp4 output.mp4 --mode face
    python vertical_video_cropper.py input.mp4 output.mp4 --mode motion
    python vertical_video_cropper.py input.mp4 output.mp4 --mode center
"""

import cv2
import numpy as np
import argparse
import sys
import os
from typing import Optional, Tuple, List


class VerticalVideoCropper:
    """智能垂直视频裁剪器"""
    
    def __init__(self, config: dict = None):
        """
        初始化裁剪器
        
        Args:
            config: 配置参数字典
        """
        self.config = config or {}
        
        # 默认配置
        self.default_config = {
            # 裁剪模式: 'face' | 'motion' | 'center'
            'mode': 'face',
            
            # 人脸检测参数
            'face_detection': {
                'scale_factor': 1.1,
                'min_neighbors': 8,
                'min_size': (30, 30),
                'sample_frames': 30,
                'right_offset': 60  # 防止右边界裁剪
            },
            
            # 运动跟踪参数
            'motion_tracking': {
                'update_interval': 1.0,  # 更新间隔(秒)
                'motion_threshold': 2.0,  # 运动检测阈值
                'smoothing_factor': 0.9,  # 平滑系数(0-1)
                'scale_factor': 0.67,  # 缩放比例
                'max_shifts_per_second': 1  # 每秒最大移动次数
            },
            
            # 输出参数
            'output': {
                'codec': 'mp4v',
                'fps': None,  # 保持原视频FPS
                'quality': 'medium',  # 输出质量
                'bitrate': '3000k'
            }
        }
        
        # 合并配置
        self._merge_config()
        
        # 加载人脸检测器
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
    def _merge_config(self):
        """合并配置参数"""
        if not self.config:
            self.config = self.default_config
            return
            
        # 深度合并配置
        def deep_merge(base, override):
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value
        
        deep_merge(self.default_config, self.config)
        self.config = self.default_config
    
    def crop_to_vertical(self, input_video_path: str, output_video_path: str) -> bool:
        """
        将横屏视频裁剪为9:16垂直格式
        
        Args:
            input_video_path: 输入视频路径
            output_video_path: 输出视频路径
            
        Returns:
            bool: 裁剪是否成功
        """
        try:
            # 打开视频文件
            cap = cv2.VideoCapture(input_video_path, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                print(f"错误: 无法打开视频文件 {input_video_path}")
                return False
            
            # 获取视频信息
            original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            print(f"输入视频: {original_width}x{original_height}, {fps:.2f} FPS, {total_frames} 帧")
            
            # 计算输出尺寸 (9:16)
            vertical_height = int(original_height)
            vertical_width = int(vertical_height * 9 / 16)
            
            print(f"输出尺寸: {vertical_width}x{vertical_height} (9:16)")
            
            # 检查输入视频尺寸
            if original_width < vertical_width:
                print(f"错误: 输入视频宽度({original_width})小于目标宽度({vertical_width})")
                cap.release()
                return False
            
            # 根据模式选择裁剪策略
            mode = self.config['mode']
            crop_strategy = self._get_crop_strategy(mode)
            
            if not crop_strategy:
                print(f"错误: 不支持的裁剪模式 '{mode}'")
                cap.release()
                return False
            
            # 执行裁剪
            success = crop_strategy(cap, original_width, original_height, fps, 
                                  vertical_width, vertical_height, output_video_path)
            
            cap.release()
            return success
            
        except Exception as e:
            print(f"裁剪过程中发生错误: {str(e)}")
            return False
    
    def _get_crop_strategy(self, mode: str):
        """获取裁剪策略函数"""
        strategies = {
            'face': self._crop_with_face_detection,
            'motion': self._crop_with_motion_tracking,
            'center': self._crop_center
        }
        return strategies.get(mode)
    
    def _crop_with_face_detection(self, cap, original_width, original_height, fps, 
                                 vertical_width, vertical_height, output_path) -> bool:
        """动态人脸检测裁剪模式 - 实时检测并跟踪人脸"""
        print("使用动态人脸检测模式...")
        
        face_config = self.config['face_detection']
        
        # 重置视频到开始位置
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        # 初始化变量
        current_x = (original_width - vertical_width) // 2  # 默认中心位置
        face_detected = False
        last_face_x = current_x
        face_count = 0
        
        def dynamic_face_crop_function(frame):
            nonlocal current_x, face_detected, last_face_x, face_count
            
            # 每帧检测人脸
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray, 
                scaleFactor=face_config['scale_factor'],
                minNeighbors=face_config['min_neighbors'],
                minSize=face_config['min_size']
            )
            
            if len(faces) > 0:
                # 检测到人脸，选择最大的
                best_face = max(faces, key=lambda f: f[2] * f[3])
                x, y, w, h = best_face
                face_center_x = x + w // 2
                
                # 向右偏移防止右边界裁剪
                face_center_x += face_config['right_offset']
                
                if not face_detected:
                    print(f"✓ 第{face_count}帧开始检测到人脸，切换到动态跟踪")
                    face_detected = True
                
                # 计算目标裁剪位置
                target_x = max(0, min(face_center_x - vertical_width // 2, original_width - vertical_width))
                
                # 平滑移动：90%当前位置 + 10%新位置
                smoothing_factor = 0.9
                current_x = int(smoothing_factor * current_x + (1 - smoothing_factor) * target_x)
                
                last_face_x = face_center_x
                face_count += 1
            else:
                # 未检测到人脸
                if face_detected:
                    # 之前有人脸，短暂保持当前位置
                    pass
                else:
                    # 一直没有人脸，使用中心位置
                    current_x = (original_width - vertical_width) // 2
            
            # 裁剪当前帧
            crop_x_start = int(current_x)
            crop_x_end = min(crop_x_start + vertical_width, original_width)
            
            # 确保完整宽度
            if crop_x_end - crop_x_start < vertical_width:
                crop_x_start = max(0, crop_x_end - vertical_width)
            
            return frame[:, crop_x_start:crop_x_end]
        
        # 执行裁剪
        success = self._write_cropped_video(cap, vertical_width, vertical_height, fps, 
                                          output_path, dynamic_face_crop_function)
        
        # 输出统计信息
        if face_count > 0:
            print(f"✓ 成功跟踪了 {face_count} 帧中的人脸")
        else:
            print("✗ 整个视频中未检测到人脸，使用中心裁剪")
        
        return success
    
    def _crop_with_motion_tracking(self, cap, original_width, original_height, fps,
                                  vertical_width, vertical_height, output_path) -> bool:
        """运动跟踪裁剪模式"""
        print("使用运动跟踪模式...")
        
        motion_config = self.config['motion_tracking']
        
        # 计算缩放参数
        target_display_width = original_width * motion_config['scale_factor']
        scale = vertical_width / target_display_width
        scaled_width = int(original_width * scale)
        scaled_height = int(original_height * scale)
        
        # 调整缩放比例以适应高度限制
        if scaled_height > vertical_height:
            scale = vertical_height / original_height
            scaled_width = int(original_width * scale)
            scaled_height = int(original_height * scale)
        
        print(f"缩放视频: {original_width}x{original_height} → {scaled_width}x{scaled_height}")
        print(f"显示区域: {vertical_width}px 宽 (从 {scaled_width}px 缩放帧中)")
        
        # 计算更新间隔
        update_interval = max(1, int(fps * motion_config['update_interval']))
        print(f"运动跟踪: 每 {update_interval} 帧更新 (~{motion_config['update_interval']}秒)")
        
        # 重置视频到开始位置
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        smoothed_x = 0
        prev_gray = None
        
        def motion_crop_function(frame):
            nonlocal smoothed_x, prev_gray
            
            # 缩放帧
            resized_frame = cv2.resize(frame, (scaled_width, scaled_height), 
                                     interpolation=cv2.INTER_LANCOS4)
            
            # 运动跟踪逻辑
            frame_count = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            
            if frame_count % update_interval == 0:
                curr_gray = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2GRAY)
                
                if prev_gray is not None:
                    # 计算光流
                    flow = cv2.calcOpticalFlowFarneback(
                        prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
                    )
                    magnitude = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
                    
                    # 检测显著运动
                    significant_motion = magnitude > motion_config['motion_threshold']
                    
                    if np.any(significant_motion):
                        # 按运动权重计算焦点位置
                        col_motion = np.sum(magnitude * significant_motion, axis=0)
                        
                        if np.sum(col_motion) > 0:
                            motion_x = int(np.average(np.arange(scaled_width), weights=col_motion))
                            target_x = max(0, min(motion_x - vertical_width // 2, scaled_width - vertical_width))
                            
                            # 平滑移动
                            smoothing = motion_config['smoothing_factor']
                            smoothed_x = int(smoothing * smoothed_x + (1 - smoothing) * target_x)
                
                prev_gray = curr_gray
            
            # 裁剪缩放后的帧
            crop_x_start = int(smoothed_x)
            crop_x_end = min(crop_x_start + vertical_width, scaled_width)
            
            # 确保完整宽度
            if crop_x_end - crop_x_start < vertical_width:
                crop_x_start = max(0, crop_x_end - vertical_width)
            
            cropped_frame = resized_frame[:, crop_x_start:crop_x_end]
            
            # 处理高度适配
            if scaled_height < vertical_height:
                canvas = np.zeros((vertical_height, vertical_width, 3), dtype=np.uint8)
                offset_y = (vertical_height - scaled_height) // 2
                canvas[offset_y:offset_y+scaled_height, :] = cropped_frame
                cropped_frame = canvas
            elif scaled_height > vertical_height:
                cropped_frame = cropped_frame[:vertical_height, :]
            
            return cropped_frame
        
        return self._write_cropped_video(cap, vertical_width, vertical_height, fps,
                                       output_path, motion_crop_function)
    
    def _crop_center(self, cap, original_width, original_height, fps,
                    vertical_width, vertical_height, output_path) -> bool:
        """中心裁剪模式"""
        print("使用中心裁剪模式...")
        
        x_start = (original_width - vertical_width) // 2
        print(f"中心裁剪位置: x={x_start}")
        
        # 重置视频到开始位置
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        return self._write_cropped_video(cap, vertical_width, vertical_height, fps,
                                       output_path, lambda frame: frame[:, x_start:x_start+vertical_width])
    
    def _write_cropped_video(self, cap, width, height, fps, output_path, crop_function) -> bool:
        """写入裁剪后的视频"""
        try:
            fourcc = cv2.VideoWriter_fourcc(*self.config['output']['codec'])
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            if not out.isOpened():
                print(f"错误: 无法创建输出视频文件 {output_path}")
                return False
            
            frame_count = 0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            print(f"开始处理 {total_frames} 帧...")
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 应用裁剪函数
                try:
                    cropped_frame = crop_function(frame)
                    
                    # 检查裁剪后的帧尺寸
                    if cropped_frame is None or cropped_frame.shape[0] == 0 or cropped_frame.shape[1] == 0:
                        print(f"警告: 第 {frame_count} 帧裁剪后尺寸异常")
                        continue
                        
                    # 确保帧尺寸与输出设置一致
                    if cropped_frame.shape[0] != height or cropped_frame.shape[1] != width:
                        cropped_frame = cv2.resize(cropped_frame, (width, height))
                        
                    # 检查数据类型和通道数
                    if cropped_frame.dtype != np.uint8:
                        cropped_frame = cropped_frame.astype(np.uint8)
                        
                    if len(cropped_frame.shape) == 2:  # 灰度图
                        cropped_frame = cv2.cvtColor(cropped_frame, cv2.COLOR_GRAY2BGR)
                    elif cropped_frame.shape[2] == 4:  # RGBA转RGB
                        cropped_frame = cropped_frame[:, :, :3]
                        
                    out.write(cropped_frame)
                    frame_count += 1
                    
                    if frame_count % 100 == 0:
                        print(f"已处理 {frame_count}/{total_frames} 帧 ({frame_count/total_frames*100:.1f}%)")
                        
                except Exception as frame_error:
                    print(f"警告: 处理第 {frame_count} 帧时出错: {frame_error}")
                    continue
            
            out.release()
            print(f"✓ 裁剪完成: 处理了 {frame_count} 帧 -> {output_path}")
            return True
            
        except Exception as e:
            print(f"写入视频时发生错误: {str(e)}")
            # 尝试释放资源
            try:
                if 'out' in locals():
                    out.release()
            except:
                pass
            return False


def main():
    """命令行入口函数"""
    parser = argparse.ArgumentParser(description='智能垂直视频裁剪工具')
    parser.add_argument('input', help='输入视频文件路径')
    parser.add_argument('output', help='输出视频文件路径')
    parser.add_argument('--mode', choices=['face', 'motion', 'center'], 
                       default='face', help='裁剪模式 (默认: face)')
    parser.add_argument('--scale-factor', type=float, default=0.67,
                       help='运动跟踪模式下的缩放比例 (默认: 0.67)')
    parser.add_argument('--update-interval', type=float, default=1.0,
                       help='运动跟踪更新间隔(秒) (默认: 1.0)')
    parser.add_argument('--smoothing', type=float, default=0.9,
                       help='运动跟踪平滑系数 (默认: 0.9)')
    
    args = parser.parse_args()
    
    # 检查输入文件是否存在
    if not os.path.exists(args.input):
        print(f"错误: 输入文件不存在 {args.input}")
        sys.exit(1)
    
    # 创建配置
    config = {
        'mode': args.mode,
        'motion_tracking': {
            'scale_factor': args.scale_factor,
            'update_interval': args.update_interval,
            'smoothing_factor': args.smoothing
        }
    }
    
    # 创建裁剪器并执行裁剪
    cropper = VerticalVideoCropper(config)
    success = cropper.crop_to_vertical(args.input, args.output)
    
    if success:
        print("✓ 视频裁剪成功完成!")
        sys.exit(0)
    else:
        print("✗ 视频裁剪失败")
        sys.exit(1)


if __name__ == "__main__":
    main()