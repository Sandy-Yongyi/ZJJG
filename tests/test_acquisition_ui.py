import unittest
import sys

import wx

from view.MainFrame import MainFrame
from control.MainFrameControl import MainFrameController


class AcquisitionLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)

    def setUp(self):
        self.frame = MainFrame(None)
        self.frame.Maximize(False)
        self.frame.SetSize((1280, 800))
        self.frame.Layout()
        self.frame.SendSizeEvent()
        self.app.Yield()

    def tearDown(self):
        self.frame.Destroy()
        self.app.Yield()

    def test_only_start_and_stop_buttons_remain(self):
        def descendants(window):
            for child in window.GetChildren():
                yield child
                yield from descendants(child)

        buttons = [window for window in descendants(self.frame) if isinstance(window, wx.Button)]
        self.assertEqual(set(buttons), {self.frame.start_btn, self.frame.stop_btn})
        self.assertTrue(self.frame.start_btn.IsEnabled())
        self.assertFalse(self.frame.stop_btn.IsEnabled())
        self.frame.on_program_started()
        self.assertTrue(self.frame.stop_btn.IsEnabled())
        self.frame.on_program_stopped()
        self.assertFalse(self.frame.stop_btn.IsEnabled())

    def test_output_is_below_controls_and_canvas_fills_right_side(self):
        output = self.frame.status_text.GetScreenRect()
        start = self.frame.start_btn.GetScreenRect()
        stop = self.frame.stop_btn.GetScreenRect()
        canvas = self.frame.gl_canvas.GetScreenRect()
        self.assertGreater(output.y, max(start.GetBottom(), stop.GetBottom()))
        self.assertGreater(canvas.x, output.GetRight())
        self.assertGreater(canvas.width, output.width)
        self.assertGreater(output.height, 500)
        self.assertGreater(canvas.height, 650)

    def test_buttons_are_gray_before_start_and_after_stop(self):
        def color(button):
            value = button.GetBackgroundColour()
            return value.Red(), value.Green(), value.Blue()

        for button in (self.frame.start_btn, self.frame.stop_btn):
            self.assertEqual(color(button), (180, 180, 180))
        self.frame.on_program_started()
        self.assertEqual(color(self.frame.start_btn), (87, 155, 87))
        self.assertEqual(color(self.frame.stop_btn), (224, 80, 60))
        self.assertFalse(self.frame.start_btn.IsEnabled())
        self.assertTrue(self.frame.stop_btn.IsEnabled())
        self.frame.on_program_stopped()
        for button in (self.frame.start_btn, self.frame.stop_btn):
            self.assertEqual(color(button), (180, 180, 180))
        self.assertTrue(self.frame.start_btn.IsEnabled())
        self.assertFalse(self.frame.stop_btn.IsEnabled())

    def test_controller_initializes_without_parameter_widgets(self):
        stdout, stderr = sys.stdout, sys.stderr
        controller = None
        try:
            controller = MainFrameController(None)
        finally:
            sys.stdout, sys.stderr = stdout, stderr
        try:
            self.assertFalse(controller.running)
            self.assertTrue(controller.start_btn.IsEnabled())
            self.assertFalse(controller.stop_btn.IsEnabled())
        finally:
            if controller is not None:
                controller.Destroy()


if __name__ == "__main__":
    unittest.main()
