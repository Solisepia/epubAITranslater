"""
Simple Installer for epub2zh-faithful-client
Extracts and launches the application
"""
import os
import sys
import tempfile
import shutil
import zipfile
from pathlib import Path

def main():
    # 获取安装包所在目录
    if getattr(sys, 'frozen', False):
        installer_dir = Path(sys.executable).parent
    else:
        installer_dir = Path(__file__).parent
    
    # 查找嵌入的 ZIP 文件
    zip_files = list(installer_dir.glob('epub2zh-faithful-client-*.zip'))
    
    if not zip_files:
        print("Error: Client ZIP file not found!")
        input("Press Enter to exit...")
        return 1
    
    client_zip = zip_files[0]
    
    # 创建临时解压目录
    temp_dir = Path(tempfile.gettempdir()) / "epub2zh-installer"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()
    
    print(f"Extracting {client_zip.name}...")
    
    # 解压 ZIP
    with zipfile.ZipFile(client_zip, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)
    
    # 查找主程序
    client_dir = temp_dir / "epub2zh-faithful-client"
    if not client_dir.exists():
        # 尝试直接在根目录
        client_dir = temp_dir
    
    exe_file = client_dir / "epub2zh-faithful-client.exe"
    
    if not exe_file.exists():
        print("Error: Main executable not found!")
        input("Press Enter to exit...")
        return 1
    
    # 选择安装目录
    print("\nepub2zh-faithful-client Installer")
    print("=" * 50)
    
    default_install = Path(os.environ.get('PROGRAMFILES', 'C:\\Program Files')) / "epub2zh-faithful-client"
    install_dir = input(f"\nInstall to [Enter for {default_install}]: ").strip()
    
    if not install_dir:
        install_dir = default_install
    
    install_dir = Path(install_dir)
    
    # 创建安装目录
    try:
        install_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        print(f"\nError: Cannot create directory. Please run as Administrator.")
        input("Press Enter to exit...")
        return 1
    
    # 复制文件
    print(f"\nInstalling to {install_dir}...")
    for item in client_dir.iterdir():
        dest = install_dir / item.name
        print(f"  Copying {item.name}...")
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    
    # 创建快捷方式
    print("\nCreating shortcuts...")
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        
        # 开始菜单快捷方式
        start_menu = Path(os.environ.get('APPDATA')) / "Microsoft/Windows/Start Menu/Programs"
        shortcut = shell.CreateShortCut(str(start_menu / "epub2zh-faithful-client.lnk"))
        shortcut.TargetPath = str(install_dir / "epub2zh-faithful-client.exe")
        shortcut.WorkingDirectory = str(install_dir)
        shortcut.save()
        
        # 桌面快捷方式
        desktop = Path(os.environ.get('USERPROFILE')) / "Desktop"
        shortcut = shell.CreateShortCut(str(desktop / "epub2zh-faithful-client.lnk"))
        shortcut.TargetPath = str(install_dir / "epub2zh-faithful-client.exe")
        shortcut.WorkingDirectory = str(install_dir)
        shortcut.save()
        
        print("  Shortcuts created.")
    except Exception as e:
        print(f"  Warning: Could not create shortcuts: {e}")
    
    # 清理临时文件
    print("\nCleaning up...")
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    print("\n" + "=" * 50)
    print("Installation complete!")
    print("=" * 50)
    
    # 询问是否启动
    launch = input("\nLaunch epub2zh-faithful-client now? [Y/n]: ").strip().lower()
    if launch != 'n':
        print(f"\nStarting {exe_file.name}...")
        os.startfile(str(exe_file))
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
