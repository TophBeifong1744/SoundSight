# Pillow兼容修复

用户板端原6项测试：5通过，导航绘制1错误。原错误：

```text
ui.py: while value and draw.textbbox((0, 0), value, font=font)[2] > 780-x:
AttributeError: ImageDraw object has no attribute textbbox
```

实际UI增加textsize回退，保持文字裁切。新增测试以旧API代理真实画笔，覆盖四页绘制、180度导航且不开轴。板端复测待用户执行，不更改位流。
