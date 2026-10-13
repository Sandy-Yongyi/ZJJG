import wx
import os
# import sys
# # 将项目的根目录添加到 sys.path 中
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from model.plot.PointCloudCanvas import PointCloudCanvas


# 颜色常量定义
BG_COLOR_LIGHT_GREEN = wx.Colour(240, 250, 250)  # 浅绿色背景
BG_COLOR_WHITE = wx.WHITE
BG_COLOR_GREEN = wx.Colour(107, 175, 107)  # 绿色（开始按钮）
BG_COLOR_RED = wx.Colour(244, 100, 80)  # 红色（结束按钮）
BG_COLOR_BLUE = wx.Colour(150, 230, 244)  # 钻石蓝（参数按钮）


class BorderedPanel(wx.Panel):
    """带明显黑色边框的面板"""

    def __init__(self, parent, label="", bg_color=None):
        super().__init__(parent)
        self.label = label
        self.bg_color = bg_color or wx.Colour(220, 247, 221)
        self.SetBackgroundColour(self.bg_color)
        self.Bind(wx.EVT_PAINT, self._on_paint)

    def _on_paint(self, event):
        """绘制黑色边框"""
        dc = wx.PaintDC(self)
        rect = self.GetClientRect()

        # 绘制背景
        dc.SetBrush(wx.Brush(self.bg_color))
        dc.DrawRectangle(rect)

        # 绘制粗黑色边框（3像素）
        dc.SetPen(wx.Pen(wx.BLACK, 3))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(0, 0, rect.width, rect.height)

        # 绘制标签（如果有）
        if self.label:
            font = wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)  # 改为普通字体，不加粗
            dc.SetFont(font)
            dc.SetTextForeground(wx.BLACK)
            text_width, text_height = dc.GetTextExtent(self.label)

            # 标签位置：顶部左侧，内缩一点，向下间隔10像素
            label_x = 15
            label_y = 15

            # 在标签周围地方画白色背景来遮挡边框
            bg_margin = 3  # 标签周围的白色边距
            dc.SetBrush(wx.Brush(self.bg_color))
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.DrawRectangle(label_x - bg_margin, label_y - bg_margin, text_width + 2 * bg_margin, text_height + 2 * bg_margin)

            # 绘制标签文字
            dc.DrawText(self.label, label_x, label_y)


class ModernButton(wx.Button):
    """现代化按钮类 - 所有按钮显示darker效果和边框"""

    def __init__(self, parent, label, size=wx.Size(150, 50), bg_color=None, text_color=None):
        super().__init__(parent, label=label, size=size)
        self.bg_color = bg_color or BG_COLOR_BLUE  # 原始背景色
        self.text_color = text_color or wx.BLACK  # 文字颜色
        self.disabled_color = wx.Colour(180, 180, 180)  # 禁用时的灰色
        self.visual_active = True
        self.current_text_color = self.text_color

        # 使用普通字体（不加粗）来避免文字重叠
        font = wx.Font(13, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(font)

        # 绑定Paint事件
        self.Bind(wx.EVT_PAINT, self._on_paint)

        # 初始化颜色
        self._update_button_appearance()

    def _update_button_appearance(self):
        """根据启用/禁用状态更新按钮外观"""
        if self.visual_active:
            # 启用时：使用darker效果（减20）
            self.current_bg = wx.Colour(max(0, self.bg_color.red - 20), max(0, self.bg_color.green - 20), max(0, self.bg_color.blue - 20))
            self.current_text_color = self.text_color
        else:
            # 禁用时：使用灰色
            self.current_bg = self.disabled_color
            self.current_text_color = wx.BLACK

        self.SetBackgroundColour(self.current_bg)
        self.SetForegroundColour(self.current_text_color)

    def SetVisualActive(self, active=True):
        """仅控制按钮是否显示彩色外观，不影响点击能力"""
        self.visual_active = active
        self._update_button_appearance()
        self.Refresh()

    def Enable(self, enable=True):
        """重写Enable方法以更新按钮外观"""
        super().Enable(enable)
        self._update_button_appearance()
        self.Refresh()

    def _on_paint(self, event):
        """自定义绘制 - 显示darker效果和边框"""
        dc = wx.PaintDC(self)
        rect = self.GetClientRect()

        # 绘制主背景
        dc.SetBrush(wx.Brush(self.current_bg))
        dc.SetPen(wx.Pen(self.current_bg))
        dc.DrawRectangle(rect)

        # 绘制深色边框（3像素）给按钮凹陷感
        border_color = wx.Colour(max(0, self.current_bg.red - 30), max(0, self.current_bg.green - 30), max(0, self.current_bg.blue - 30))
        dc.SetPen(wx.Pen(border_color, 2))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(0, 0, rect.width - 1, rect.height - 1)

        # 获取文字
        label = self.GetLabel()
        font = self.GetFont()
        dc.SetFont(font)

        # 测量文字尺寸
        text_width, text_height = dc.GetTextExtent(label)
        x = (rect.width - text_width) // 2
        y = (rect.height - text_height) // 2

        # 绘制文字
        dc.SetTextForeground(self.current_text_color)
        dc.DrawText(label, x, y)


class MainFrame(wx.Frame):
    """左侧采集控制及输出，右侧为完整的 3D 点云显示区域。"""

    def __init__(self, parent):
        super().__init__(parent, title="Joihey Software")
        self.SetBackgroundColour(BG_COLOR_LIGHT_GREEN)
        self.SetMinSize(wx.Size(800, 480))
        self.SetFont(wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT))
        icon_path = os.path.join(os.path.dirname(__file__), "..", "data", "picture", "junhe.ico")
        if os.path.exists(icon_path):
            self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO))
        self.InitUI()
        self._set_control_buttons_active(False)

    def InitUI(self):
        panel = wx.Panel(self)
        panel.SetBackgroundColour(BG_COLOR_LIGHT_GREEN)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 左栏保持固定宽度；输出框随窗口高度填充按钮下方的空间。
        self.control_panel = wx.Panel(panel, size=wx.Size(360, -1))
        self.control_panel.SetMinSize(wx.Size(360, -1))
        self.control_panel.SetBackgroundColour(wx.Colour(240, 240, 240))
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        control_box = wx.StaticBox(self.control_panel, label="采集控制")
        control_sizer = wx.StaticBoxSizer(control_box, wx.VERTICAL)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.start_btn = ModernButton(
            control_box, label="开始", size=wx.Size(145, 44), bg_color=BG_COLOR_GREEN,
        )
        self.stop_btn = ModernButton(
            control_box, label="结束", size=wx.Size(145, 44), bg_color=BG_COLOR_RED,
        )
        button_sizer.Add(self.start_btn, 1, wx.EXPAND | wx.ALL, 5)
        button_sizer.Add(self.stop_btn, 1, wx.EXPAND | wx.ALL, 5)
        control_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 5)
        left_sizer.Add(control_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.status_panel = wx.Panel(self.control_panel)
        status_sizer = wx.BoxSizer(wx.VERTICAL)
        status_sizer.Add(wx.StaticText(self.status_panel, label="运行输出"), 0, wx.BOTTOM, 5)
        self.status_text = wx.TextCtrl(
            self.status_panel, style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        self.status_text.SetInsertionPointEnd()
        status_sizer.Add(self.status_text, 1, wx.EXPAND)
        self.status_panel.SetSizer(status_sizer)
        left_sizer.Add(self.status_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.control_panel.SetSizer(left_sizer)

        # 右栏全部用于点云画布，不再放置输出框或设备参数控件。
        self.point_cloud_panel = wx.Panel(panel)
        self.point_cloud_panel.SetBackgroundColour(wx.Colour(200, 200, 200))
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        title = wx.StaticText(self.point_cloud_panel, label="3D 点云显示")
        right_sizer.Add(title, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 8)
        self.gl_canvas = PointCloudCanvas(self.point_cloud_panel)
        right_sizer.Add(self.gl_canvas, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        self.point_cloud_panel.SetSizer(right_sizer)

        main_sizer.Add(self.control_panel, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(self.point_cloud_panel, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(main_sizer)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(frame_sizer)

    def _set_param_buttons_enabled(self, enabled: bool):
        pass  # 参数配置控件已移除

    def _set_control_buttons_active(self, active: bool):
        self.start_btn.SetVisualActive(active)
        self.stop_btn.SetVisualActive(active)
        self.start_btn.Enable(not active)
        self.stop_btn.Enable(active)

    def on_program_started(self):
        self._set_control_buttons_active(True)

    def on_program_stopped(self):
        self._set_control_buttons_active(False)


if __name__ == "__main__":
    app = wx.App()
    frame = MainFrame(None)
    frame.Maximize(True)
    frame.Show()
    app.MainLoop()
