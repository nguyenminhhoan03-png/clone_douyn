import shutil
import pathlib
d = pathlib.Path(r'E:\Project_ItWebDev\Python\tiktok-upload-video\config\cookies\admin\.profiles')
if d.exists():
    shutil.rmtree(d, ignore_errors=True)
    print("Deleted")
else:
    print("Not found")
