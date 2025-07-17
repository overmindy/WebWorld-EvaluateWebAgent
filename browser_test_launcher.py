#!/usr/bin/env python3
"""
简单的浏览器环境启动器 - 用于测试文本信息提取功能
Simple Browser Environment Launcher - For testing text extraction capabilities
"""

import asyncio
import json
from pathlib import Path
from typing import Optional
from agent_eval.environment.web_environment import WebEnvironment

class BrowserTestLauncher:
    """简单的浏览器测试启动器"""
    
    def __init__(self):
        self.env: Optional[WebEnvironment] = None
        self.config = {
            "browser": {
                "type": "chromium",
                "headless": False,  # 设置为False以便你可以看到浏览器
                "viewport": {"width": 1280, "height": 720},
                "timeout": 30000
            }
        }
    
    async def start_browser(self):
        """启动浏览器环境"""
        print("🚀 启动浏览器环境...")
        self.env = WebEnvironment(self.config)
        await self.env.initialize()
        print("✅ 浏览器环境已启动")
        return True
    
    async def navigate_to_url(self, url: str):
        """导航到指定URL"""
        if not self.env:
            print("❌ 浏览器环境未启动")
            return False
        
        print(f"🌐 导航到: {url}")
        success = await self.env.launch_webpage(url)
        if success:
            print("✅ 页面加载成功")
        else:
            print("❌ 页面加载失败")
        return success
    
    async def extract_html_text(self, viewport_only: bool = True):
        """提取HTML文本信息"""
        if not self.env:
            print("❌ 浏览器环境未启动")
            return None
        
        print("📄 提取HTML文本信息...")
        html_text = await self.env.get_page_text_info("html", viewport_only)
        print(f"✅ HTML文本提取完成，长度: {len(html_text)} 字符")
        return html_text
    
    async def extract_accessibility_text(self, viewport_only: bool = True):
        """提取可访问性树文本信息"""
        if not self.env:
            print("❌ 浏览器环境未启动")
            return None
        
        print("🌳 提取可访问性树文本信息...")
        accessibility_text = await self.env.get_page_text_info("accessibility_tree", viewport_only)
        print(f"✅ 可访问性文本提取完成，长度: {len(accessibility_text)} 字符")
        return accessibility_text
    
    async def get_combined_info(self):
        """获取综合页面信息"""
        if not self.env:
            print("❌ 浏览器环境未启动")
            return None
        
        print("📊 获取综合页面信息...")
        combined_info = await self.env.get_combined_page_info(
            include_screenshot=True,
            include_html=True,
            include_accessibility_tree=True,
            current_viewport_only=True
        )
        
        print("✅ 综合信息获取完成:")
        print(f"  - 截图: {'✅' if combined_info.get('screenshot') else '❌'}")
        print(f"  - HTML文本: {'✅' if combined_info.get('html_text') else '❌'}")
        print(f"  - 可访问性文本: {'✅' if combined_info.get('accessibility_text') else '❌'}")
        print(f"  - 元素节点数: {len(combined_info.get('metadata', {}).get('obs_nodes_info', {}))}")
        
        return combined_info
    
    async def save_text_to_file(self, text: str, filename: str):
        """保存文本到文件"""
        try:
            output_path = Path(filename)
            output_path.write_text(text, encoding='utf-8')
            print(f"💾 文本已保存到: {output_path.absolute()}")
            return True
        except Exception as e:
            print(f"❌ 保存文件失败: {e}")
            return False
    
    async def find_clickable_elements(self):
        """查找可点击的元素"""
        if not self.env:
            print("❌ 浏览器环境未启动")
            return []
        
        print("🔍 查找可点击元素...")
        metadata = await self.env.get_text_extraction_metadata()
        clickable_elements = []
        
        for element_id, node_info in metadata["obs_nodes_info"].items():
            text = node_info.get("text", "").lower()
            if any(keyword in text for keyword in ["button", "link", "click", "submit"]):
                center = await self.env.get_element_center(element_id)
                if center:
                    clickable_elements.append({
                        "id": element_id,
                        "text": node_info["text"],
                        "center": center,
                        "bounds": node_info.get("union_bound")
                    })
        
        print(f"✅ 找到 {len(clickable_elements)} 个可点击元素")
        return clickable_elements
    
    async def click_element_by_id(self, element_id: str):
        """通过元素ID点击元素"""
        if not self.env:
            print("❌ 浏览器环境未启动")
            return False
        
        center = await self.env.get_element_center(element_id)
        if not center:
            print(f"❌ 无法获取元素 {element_id} 的坐标")
            return False
        
        # 转换为屏幕坐标
        viewport = await self.env.page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")
        x = int(center[0] * viewport["width"])
        y = int(center[1] * viewport["height"])
        
        print(f"🖱️ 点击元素 {element_id} 在坐标 ({x}, {y})")
        success = await self.env.click(x, y)
        if success:
            print("✅ 点击成功")
        else:
            print("❌ 点击失败")
        return success
    
    async def cleanup(self):
        """清理资源"""
        if self.env:
            print("🧹 清理浏览器资源...")
            await self.env.cleanup()
            print("✅ 清理完成")

async def interactive_test():
    """交互式测试函数"""
    launcher = BrowserTestLauncher()
    
    try:
        # 启动浏览器
        await launcher.start_browser()
        
        print("\n" + "="*60)
        print("🎯 浏览器测试启动器已就绪!")
        print("请在下面输入要访问的网页URL，然后我们可以测试各种文本提取功能")
        print("="*60)
        
        while True:
            print("\n📋 可用命令:")
            print("1. url <网址>           - 导航到指定网页")
            print("2. html                 - 提取HTML文本信息")
            print("3. accessibility        - 提取可访问性树文本信息")
            print("4. combined             - 获取综合页面信息")
            print("5. save_html <文件名>   - 保存HTML文本到文件")
            print("6. save_acc <文件名>    - 保存可访问性文本到文件")
            print("7. find_clickable       - 查找可点击元素")
            print("8. click <元素ID>       - 点击指定元素")
            print("9. quit                 - 退出")
            
            command = input("\n💬 请输入命令: ").strip()
            
            if command.startswith("url "):
                url = command[4:].strip()
                await launcher.navigate_to_url(url)
                
            elif command == "html":
                html_text = await launcher.extract_html_text()
                if html_text:
                    print("\n📄 HTML文本信息 (前500字符):")
                    print("-" * 50)
                    print(html_text[:500] + ("..." if len(html_text) > 500 else ""))
                    
            elif command == "accessibility":
                acc_text = await launcher.extract_accessibility_text()
                if acc_text:
                    print("\n🌳 可访问性文本信息 (前500字符):")
                    print("-" * 50)
                    print(acc_text[:500] + ("..." if len(acc_text) > 500 else ""))
                    
            elif command == "combined":
                await launcher.get_combined_info()
                
            elif command.startswith("save_html "):
                filename = command[10:].strip()
                html_text = await launcher.extract_html_text()
                if html_text:
                    await launcher.save_text_to_file(html_text, filename)
                    
            elif command.startswith("save_acc "):
                filename = command[9:].strip()
                acc_text = await launcher.extract_accessibility_text()
                if acc_text:
                    await launcher.save_text_to_file(acc_text, filename)
                    
            elif command == "find_clickable":
                elements = await launcher.find_clickable_elements()
                if elements:
                    print("\n🔍 可点击元素列表:")
                    for i, elem in enumerate(elements[:10]):  # 只显示前10个
                        print(f"  {i+1}. ID: {elem['id']}")
                        print(f"     文本: {elem['text'][:100]}...")
                        print(f"     坐标: {elem['center']}")
                        print()
                        
            elif command.startswith("click "):
                element_id = command[6:].strip()
                await launcher.click_element_by_id(element_id)
                
            elif command == "quit":
                break
                
            else:
                print("❌ 未知命令，请重新输入")
    
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await launcher.cleanup()

if __name__ == "__main__":
    print("🌐 浏览器文本提取测试启动器")
    print("=" * 50)
    asyncio.run(interactive_test())
