import sys
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QMainWindow,
    QGraphicsBlurEffect,
    QGraphicsOpacityEffect,
)
from PyQt5.QtCore import (
    Qt,
    QPropertyAnimation,
    QRect,
    QPoint,
    QSize,
    QTimer,
    QEasingCurve,
    QEvent,
    QRectF,
)
from PyQt5.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QBrush,
    QLinearGradient,
    QRadialGradient,
    QCursor,
    QPen,
    QPixmap,
    QImage,
)
import random
import platform


class FloatingPanel(QWidget):
    def __init__(self):
        super().__init__()

        # 设置窗口属性
        self.setWindowFlags(
            Qt.FramelessWindowHint  # 无边框
            | Qt.WindowStaysOnTopHint  # 置顶窗口
            | Qt.Tool  # 不在任务栏显示
        )
        self.setAttribute(Qt.WA_TranslucentBackground)  # 背景透明

        # 跟踪状态
        self.should_close = False
        self.last_leave_time = 0

        # 获取屏幕信息
        screen = QApplication.primaryScreen().geometry()
        self.screen_width = screen.width()
        self.screen_height = screen.height()

        # 设置窗口尺寸和位置参数
        self.panel_height = int(self.screen_height * 0.75)  # 高度为屏幕高度的75%

        # 使用16:9比例计算展开宽度
        self.expanded_width = int(self.panel_height * 16 / 9)  # 16:9比例
        self.collapsed_width = 8  # 收起宽度为8px

        # 计算展开后的中心位置
        self.expanded_x = int((self.screen_width - self.expanded_width) / 2)  # 屏幕中央

        # 初始窗口位置和大小
        self.setGeometry(
            int(self.screen_width - self.collapsed_width),  # 靠右边
            int((self.screen_height - self.panel_height) / 2),  # 垂直居中
            self.collapsed_width,  # 初始宽度
            self.panel_height,  # 高度
        )

        # 创建布局与内容
        self.initUI()

        # 悬浮窗状态
        self.is_expanded = False
        self.mouse_tracking = False
        self.noise_dots = []  # 用于绘制噪点效果
        self.generate_noise()

        # 创建截屏用于背景模糊
        self.background_image = None
        self.update_background()

        # 创建动画对象
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.finished.connect(self.animation_finished)

        # 用于检测鼠标离开窗口的计时器 - 增加到3秒
        self.leave_timer = QTimer(self)
        self.leave_timer.setSingleShot(True)
        self.leave_timer.setInterval(3000)  # 保证3秒
        self.leave_timer.timeout.connect(self.delayed_check)

        # 鼠标位置检查计时器
        self.position_check_timer = QTimer(self)
        self.position_check_timer.setInterval(500)  # 500毫秒检查一次
        self.position_check_timer.timeout.connect(self.check_mouse_position)

        # 背景刷新计时器 (用于创建动态模糊效果)
        self.background_timer = QTimer(self)
        self.background_timer.setInterval(2000)  # 每2秒刷新一次背景
        self.background_timer.timeout.connect(self.update_background)
        self.background_timer.start()

        # 显示窗口
        self.show()

        # 安装全局事件过滤器
        QApplication.instance().installEventFilter(self)

    def initUI(self):
        """初始化UI组件"""
        # 主容器
        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet("background-color: transparent;")

        # 内容布局
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(30, 40, 30, 40)
        self.layout.setSpacing(20)

        # 添加标题
        title = QLabel("宽屏Mac风格悬浮窗")
        title.setStyleSheet("color: #333333; font-size: 24px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(title)

        # 添加说明文字
        desc = QLabel(
            "这是一个宽屏16:9比例的仿macOS风格毛玻璃效果悬浮窗应用，\n简洁优雅，真正实现背景模糊效果。"
        )
        desc.setStyleSheet("color: #555555; font-size: 14px;")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        self.layout.addWidget(desc)

        self.layout.addSpacing(20)

        # 添加一些示例按钮 - macOS风格
        for i, text in enumerate(["操作一", "操作二", "操作三"]):
            btn = QPushButton(text)
            btn.setStyleSheet(
                """
                QPushButton {
                    background-color: rgba(255, 255, 255, 140);
                    color: #333333;
                    border: none;
                    border-radius: 6px;
                    padding: 10px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 180);
                }
                QPushButton:pressed {
                    background-color: rgba(200, 200, 200, 150);
                }
            """
            )
            self.layout.addWidget(btn)

        # 添加一些填充空间
        self.layout.addStretch()

        # 底部信息
        footer = QLabel("鼠标悬浮展开 · 移出自动收起 (3秒)")
        footer.setStyleSheet("color: #888888; font-size: 12px;")
        footer.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(footer)

        # 设置容器尺寸和位置
        self.container.setGeometry(0, 0, self.width(), self.height())

    def update_background(self):
        """更新背景图像以创建真实模糊效果"""
        if not self.is_expanded:
            return

        # 获取屏幕截图作为背景
        screen = QApplication.primaryScreen()
        self.background_image = screen.grabWindow(0).toImage()
        self.update()  # 触发重绘

    def generate_noise(self):
        """生成随机噪点，用于增强毛玻璃效果"""
        self.noise_dots = []
        num_dots = 300  # 增加噪点数量

        for _ in range(num_dots):
            x = random.randint(0, 100)  # 百分比位置
            y = random.randint(0, 100)  # 百分比位置
            size = random.randint(1, 4)  # 1-4像素大小
            opacity = random.randint(5, 30) / 100  # 5%-30%透明度

            self.noise_dots.append((x, y, size, opacity))

    def eventFilter(self, watched, event):
        """全局事件过滤器，用于处理鼠标移动事件"""
        if event.type() == QEvent.MouseMove:
            # 如果鼠标在窗口内，重置关闭标志
            if self.is_expanded and self.geometry().contains(QCursor.pos()):
                self.should_close = False

        return super().eventFilter(watched, event)

    def enterEvent(self, event):
        """鼠标进入窗口时触发展开动画"""
        # 停止任何收起计划
        self.leave_timer.stop()
        self.should_close = False

        if (
            not self.is_expanded
            and not self.animation.state() == QPropertyAnimation.Running
        ):
            self.expand()

    def leaveEvent(self, event):
        """鼠标离开窗口时启动计时器"""
        if self.is_expanded:
            # 开始3秒倒计时
            self.leave_timer.start()
            print("计时器启动，3秒后检查")

    def delayed_check(self):
        """在延迟后检查是否应该关闭窗口"""
        self.should_close = True
        # 启动位置检查计时器，确保只有当鼠标不在窗口附近时才关闭
        self.check_mouse_position()

    def check_mouse_position(self):
        """检查鼠标位置，决定是否收起窗口"""
        if not self.is_expanded or not self.should_close:
            return

        # 获取鼠标当前位置
        mouse_pos = QCursor.pos()

        # 计算鼠标与窗口的相对位置
        window_rect = self.geometry()

        # 添加缓冲区：窗口周围30像素的区域也算作窗口内
        buffer = 30
        extended_rect = window_rect.adjusted(-buffer, -buffer, buffer, buffer)

        # 如果鼠标不在扩展区域内，且窗口已展开，且我们应该关闭，则收起窗口
        if not extended_rect.contains(mouse_pos) and self.should_close:
            if not self.animation.state() == QPropertyAnimation.Running:
                print("窗口收起")
                self.collapse()
                self.should_close = False

    def animation_finished(self):
        """动画完成后的回调"""
        # 如果刚刚完成展开动画，更新背景并启动位置检查
        if self.is_expanded:
            self.update_background()  # 刷新背景截图
            self.position_check_timer.start()
        else:
            self.position_check_timer.stop()

    def expand(self):
        """展开窗口到屏幕中央"""
        self.position_check_timer.stop()

        # 几何形状动画
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(
            QRect(self.expanded_x, self.y(), self.expanded_width, self.panel_height)
        )
        self.animation.start()

        self.is_expanded = True

        # 调整容器尺寸
        QTimer.singleShot(
            50,
            lambda: self.container.setGeometry(
                0, 0, self.expanded_width, self.panel_height
            ),
        )

    def collapse(self):
        """收起窗口到屏幕右侧"""
        self.position_check_timer.stop()
        self.leave_timer.stop()  # 确保计时器停止

        # 几何形状动画
        target_x = int(self.screen_width - self.collapsed_width)
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(
            QRect(target_x, self.y(), self.collapsed_width, self.panel_height)
        )
        self.animation.start()

        self.is_expanded = False
        self.mouse_tracking = False

        # 调整容器尺寸
        QTimer.singleShot(
            50,
            lambda: self.container.setGeometry(
                0, 0, self.collapsed_width, self.panel_height
            ),
        )

    def resizeEvent(self, event):
        """窗口大小变化时调整容器大小"""
        self.container.setGeometry(0, 0, self.width(), self.height())

    def apply_blur(self, image, radius=10):
        """应用模糊效果到图像"""
        # 创建临时QImage用于模糊处理
        temp = QImage(image.size(), QImage.Format_ARGB32)
        temp.fill(Qt.transparent)

        # 使用QPainter在临时图像上绘制模糊效果
        painter = QPainter(temp)

        # 简单的盒式模糊算法
        w, h = image.width(), image.height()
        for dx in range(-radius, radius + 1, 2):
            for dy in range(-radius, radius + 1, 2):
                weight = (radius - abs(dx)) * (radius - abs(dy)) / (radius * radius)
                if weight <= 0:
                    continue

                # 绘制偏移图像并设置透明度
                painter.setOpacity(weight * 0.5)
                painter.drawImage(QPoint(dx, dy), image)

        painter.end()
        return temp

    def paintEvent(self, event):
        """绘制窗口背景，实现macOS风格毛玻璃效果"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 创建圆角矩形路径
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 10, 10)

        # 设置裁剪区域
        painter.setClipPath(path)

        if self.is_expanded:
            # ===== 绘制背景模糊效果 =====
            if self.background_image:
                # 获取窗口在屏幕上的位置
                window_pos = self.mapToGlobal(QPoint(0, 0))

                # 从背景图像中截取窗口位置的部分
                bg_rect = QRect(
                    window_pos.x(), window_pos.y(), self.width(), self.height()
                )

                # 确保矩形在背景图像范围内
                if (
                    bg_rect.right() <= self.background_image.width()
                    and bg_rect.bottom() <= self.background_image.height()
                ):
                    # 截取背景图像对应部分
                    window_bg = self.background_image.copy(bg_rect)

                    # 应用模糊效果
                    blurred = self.apply_blur(window_bg, radius=15)

                    # 绘制模糊后的背景
                    painter.drawImage(0, 0, blurred)

            # 绘制半透明白色背景层
            painter.fillPath(path, QBrush(QColor(255, 255, 255, 150)))

            # 添加噪点纹理以增强毛玻璃效果
            for x_percent, y_percent, size, opacity in self.noise_dots:
                x = int(self.width() * x_percent / 100)
                y = int(self.height() * y_percent / 100)

                painter.setBrush(QBrush(QColor(255, 255, 255, int(255 * opacity))))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(x, y, size, size)

            # 绘制第二层噪点，不同的大小和透明度
            for x_percent, y_percent, size, opacity in self.noise_dots[
                :80
            ]:  # 使用部分噪点
                x = int(self.width() * (100 - x_percent) / 100)  # 反向位置
                y = int(self.height() * (100 - y_percent) / 100)  # 反向位置

                painter.setBrush(
                    QBrush(QColor(0, 0, 0, int(255 * opacity * 0.4)))
                )  # 更暗的噪点
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(x, y, size, size)

            # 添加顶部渐变层 - 增加亮度
            top_gradient = QLinearGradient(0, 0, 0, 100)
            top_gradient.setColorAt(0.0, QColor(255, 255, 255, 60))
            top_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))

            top_path = QPainterPath()
            top_path.addRoundedRect(0, 0, self.width(), 100, 10, 10)
            painter.fillPath(top_path, QBrush(top_gradient))

            # 底部渐变层 - 增加深度
            bottom_gradient = QLinearGradient(0, self.height() - 80, 0, self.height())
            bottom_gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
            bottom_gradient.setColorAt(1.0, QColor(0, 0, 0, 25))

            bottom_path = QPainterPath()
            bottom_path.addRect(0, self.height() - 80, self.width(), 80)
            painter.fillPath(bottom_path, QBrush(bottom_gradient))

            # 左侧微妙高光
            left_gradient = QLinearGradient(0, 0, 40, 0)
            left_gradient.setColorAt(0.0, QColor(255, 255, 255, 40))
            left_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))

            left_path = QPainterPath()
            left_path.addRect(0, 0, 40, self.height())
            painter.fillPath(left_path, QBrush(left_gradient))

            # 绘制边框高光 - 增强立体感
            pen = painter.pen()
            pen.setColor(QColor(255, 255, 255, 70))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawRoundedRect(0, 0, self.width() - 1, self.height() - 1, 10, 10)

            # 绘制内侧边框 - 增强立体感
            pen.setColor(QColor(0, 0, 0, 20))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawRoundedRect(1, 1, self.width() - 3, self.height() - 3, 9, 9)

        else:
            # 收起状态 - 更简单的效果
            # macOS风格的微妙指示条
            if self.collapsed_width <= 10:
                # 垂直线条
                line_gradient = QLinearGradient(0, 0, 0, self.height())
                line_gradient.setColorAt(0.0, QColor(200, 200, 200, 170))
                line_gradient.setColorAt(0.5, QColor(160, 160, 160, 140))
                line_gradient.setColorAt(1.0, QColor(200, 200, 200, 170))

                painter.fillRect(
                    0, 0, self.width(), self.height(), QBrush(line_gradient)
                )

                # 添加微妙高光
                highlight_line = QLinearGradient(0, 0, self.width(), 0)
                highlight_line.setColorAt(0.0, QColor(255, 255, 255, 120))
                highlight_line.setColorAt(1.0, QColor(255, 255, 255, 40))

                painter.fillRect(0, 0, self.width(), 2, QBrush(highlight_line))
            else:
                # 如果收起宽度较大，使用轻微的毛玻璃效果
                painter.fillPath(path, QBrush(QColor(240, 240, 240, 170)))


class BlurredBackground(QWidget):
    """实现高级毛玻璃效果的背景组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.background = None

    def setBackground(self, bg):
        self.background = bg
        self.update()

    def paintEvent(self, event):
        if not self.background:
            return

        painter = QPainter(self)
        painter.drawImage(0, 0, self.background)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 设置应用样式为Fusion，更接近macOS的简约风格
    app.setStyle("Fusion")

    window = FloatingPanel()
    sys.exit(app.exec_())
