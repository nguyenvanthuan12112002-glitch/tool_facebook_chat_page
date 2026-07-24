import os
import subprocess

def send_rich_toast(title, message, app_name="Omnichannel Sales Dashboard", icon_path=None, avatar_path=None):
    if not icon_path or not os.path.exists(icon_path):
        icon_path = os.path.abspath("app_logo.png")
    
    img_src = avatar_path if (avatar_path and os.path.exists(avatar_path)) else icon_path
    img_src = os.path.abspath(img_src).replace("\\", "/")

    ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

`$template = @"
<toast duration="short">
    <visual>
        <binding template="ToastGeneric">
            <text id="1">{title}</text>
            <text id="2">{message}</text>
            <image placement="appLogoOverride" hint-crop="circle" src="file:///{img_src}"/>
        </binding>
    </visual>
</toast>
"@

`$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
`$xml.LoadXml(`$template)
`$toast = [Windows.UI.Notifications.ToastNotification]::new(`$xml)
`$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{app_name}")
`$notifier.Show(`$toast)
"""
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, timeout=5)
        print("Toast sent successfully!")
    except Exception as e:
        print("Error sending toast:", e)

if __name__ == "__main__":
    send_rich_toast(
        title="Tương tác mới - Việt Nam 24h",
        message="Phạm Trường đã bình luận: \"Sản phẩm này giá bao nhiêu ạ?\"",
        app_name="Omnichannel Sales Dashboard",
        icon_path="D:/tool_facebook_chat_page/app_logo.png"
    )
