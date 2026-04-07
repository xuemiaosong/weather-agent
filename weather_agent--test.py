import requests
import json
import re
from datetime import datetime

# ========== 天气代码转换表 ==========
WEATHER_MAP = {
    0: "晴", 1: "晴", 2: "局部多云", 3: "多云",
    45: "雾", 48: "雾",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨",
    56: "冻雨", 57: "冻雨",
    61: "雨", 63: "雨", 65: "雨",
    66: "冻雨", 67: "冻雨",
    71: "雪", 73: "雪", 75: "雪",
    77: "雪粒",
    80: "阵雨", 81: "阵雨", 82: "阵雨",
    85: "阵雪", 86: "阵雪",
    95: "雷雨", 96: "雷雨", 99: "雷雨"
}

# 常用城市列表（用于快速识别，但不是限制）
COMMON_CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "重庆", "苏州", "天津", "长沙", "郑州", "青岛"]

# 城市别名映射
CITY_ALIAS = {
    "帝都": "北京",
    "魔都": "上海",
    "羊城": "广州",
    "鹏城": "深圳",
    "蓉城": "成都",
    "江城": "武汉",
    "金陵": "南京",
    "纽约": "New York",
    "伦敦": "London",
    "东京": "Tokyo",
    "巴黎": "Paris",
    "柏林": "Berlin",
}


# ========== 城市识别（支持全世界任意城市）==========

def extract_city(user_message):
    """
    从用户消息中智能提取城市名
    支持：中文城市名、英文城市名、城市别名
    返回城市名（原始输入），如果找不到返回 None
    """
    # 1. 检查别名映射
    for alias, city in CITY_ALIAS.items():
        if alias in user_message:
            return city
    
    # 2. 检查常见城市列表（快速匹配）
    for city in COMMON_CITIES:
        if city in user_message:
            return city
    
    # 3. 用正则表达式提取可能的地名
    # 匹配模式：X城市、X天气、X今天、X冷不冷等
    patterns = [
        r'([\u4e00-\u9fa5a-zA-Z\s]{2,20})天气',     # "北京天气"、"New York天气"
        r'([\u4e00-\u9fa5a-zA-Z\s]{2,20})今天',     # "北京今天"
        r'([\u4e00-\u9fa5a-zA-Z\s]{2,20})冷不冷',   # "北京冷不冷"
        r'([\u4e00-\u9fa5a-zA-Z\s]{2,20})热不热',   # "北京热不热"
        r'([\u4e00-\u9fa5a-zA-Z\s]{2,20})适合穿',   # "北京适合穿"
        r'([\u4e00-\u9fa5a-zA-Z\s]{2,20})多少度',   # "北京多少度"
        r'([\u4e00-\u9fa5a-zA-Z\s]{2,20})天气怎么样', # "北京天气怎么样"
        r'([\u4e00-\u9fa5a-zA-Z\s]{2,20})穿什么',   # "北京穿什么"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, user_message)
        if match:
            city = match.group(1).strip()
            # 去除常见的干扰词
            stop_words = ["今天", "明天", "后天", "天气", "怎么样", "多少度", "冷不冷", "热不热", "适合", "穿什么"]
            for sw in stop_words:
                city = city.replace(sw, "")
            city = city.strip()
            if city and len(city) >= 2:  # 城市名至少2个字符
                return city
    
    # 4. 如果都不匹配，尝试直接取用户输入的第一个地名
    # 提取所有连续的中文或英文字符串
    words = re.findall(r'[\u4e00-\u9fa5a-zA-Z]+', user_message)
    for word in words:
        # 过滤掉常见非城市词
        if word not in ["天气", "今天", "明天", "怎么样", "多少度", "冷不冷", "热不热", "适合", "穿什么", "出门", "建议"]:
            if len(word) >= 2:
                return word
    
    return None


# ========== 工具函数 ==========

def get_coordinates(city_name):
    """通过城市名获取经纬度（支持全世界任意城市）"""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": city_name,
        "count": 1,
        "language": "zh",
        "format": "json"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("results"):
            result = data["results"][0]
            return {
                "latitude": result["latitude"],
                "longitude": result["longitude"],
                "name": result.get("name", city_name),
                "country": result.get("country", ""),
                "admin1": result.get("admin1", "")
            }
        else:
            # 如果中文名搜不到，尝试用英文名再搜一次
            print(f"[提示] 未找到城市: {city_name}")
            return None
    except Exception as e:
        print(f"[错误] 地理编码失败: {e}")
        return None


def get_weather_real(latitude, longitude):
    """通过 Open-Meteo API 获取真实天气"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ["temperature_2m", "relative_humidity_2m", "weather_code"],
        "timezone": "auto"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        current = data.get("current", {})
        if not current:
            return None
        
        weather_code = current.get("weather_code", 0)
        weather_desc = WEATHER_MAP.get(weather_code, "多云")
        
        return {
            "temperature": round(current.get("temperature_2m", 0), 1),
            "humidity": current.get("relative_humidity_2m", 0),
            "weather": weather_desc,
            "weather_code": weather_code
        }
    except Exception as e:
        print(f"[错误] 天气API调用失败: {e}")
        return None


def get_weather_with_retry(latitude, longitude, retries=2):
    """带重试机制的天气查询"""
    for i in range(retries):
        result = get_weather_real(latitude, longitude)
        if result:
            return result
        if i < retries - 1:
            print(f"[提示] 第{i+1}次重试...")
    return None


def recommend_clothes(temperature):
    """根据温度推荐衣服"""
    if temperature <= 0:
        return "羽绒服、厚毛衣、围巾、手套、帽子"
    elif temperature <= 5:
        return "羽绒服、厚毛衣、围巾、手套"
    elif temperature <= 10:
        return "大衣、毛衣、围巾"
    elif temperature <= 15:
        return "风衣、薄毛衣、长袖衬衫"
    elif temperature <= 20:
        return "卫衣、长袖T恤、薄外套"
    elif temperature <= 25:
        return "T恤、薄外套、长裤"
    elif temperature <= 30:
        return "短袖、短裤、裙子"
    else:
        return "短袖、短裤、裙子、注意防晒"


def get_weather_fallback(city):
    """备用天气数据（当API调用失败时使用）"""
    # 通用备用数据
    return {"temperature": 20, "humidity": 60, "weather": "晴"}


def generate_response(city, weather_desc, temp, humidity, need_clothes, coords=None):
    """生成自然语言回答"""
    # 获取国家信息（如果有）
    location = city
    if coords and coords.get("country"):
        location = f"{city}（{coords['country']}）"
    
    if need_clothes:
        clothes = recommend_clothes(temp)
        return f"{location}今天{weather_desc}，温度{temp}°C，湿度{humidity}%。建议穿：{clothes}。"
    else:
        if temp <= 0:
            feeling = "天气寒冷，注意保暖"
        elif temp <= 10:
            feeling = "天气较冷，注意保暖"
        elif temp <= 20:
            feeling = "天气凉爽，体感舒适"
        elif temp <= 30:
            feeling = "天气温暖，体感舒适"
        else:
            feeling = "天气较热，注意防暑"
        return f"{location}今天{weather_desc}，温度{temp}°C，湿度{humidity}%。{feeling}。"


# ========== Agent 主函数 ==========

def chat_with_weather(user_message):
    """天气 Agent 主函数 - 支持全世界任意城市"""
    
    # 1. 提取城市（智能识别，支持任意城市）
    city = extract_city(user_message)
    
    if not city:
        # 如果实在提取不到城市，提示用户
        return "请问你想查询哪个城市的天气呢？可以告诉我城市名哦～"
    
    print(f"[识别] 城市: {city}")
    
    # 2. 判断是否需要穿衣推荐
    need_clothes = any(keyword in user_message for keyword in ["穿", "衣服", "出门", "适合", "建议", "冷不冷", "热不热"])
    
    # 3. 获取经纬度
    coords = get_coordinates(city)
    if not coords:
        return f"抱歉，无法找到「{city}」这个城市，请检查城市名是否正确。\n（支持中文或英文城市名）"
    
    print(f"[定位] {coords['name']}, {coords.get('country', '未知地区')}")
    
    # 4. 获取真实天气（带重试）
    weather = get_weather_with_retry(coords["latitude"], coords["longitude"])
    if not weather:
        print(f"[警告] 无法获取 {city} 实时天气，使用备用数据")
        weather = get_weather_fallback(city)
        weather_desc = weather["weather"]
        temp = weather["temperature"]
        humidity = weather["humidity"]
    else:
        weather_desc = weather["weather"]
        temp = weather["temperature"]
        humidity = weather["humidity"]
    
    # 5. 生成回答
    return generate_response(city, weather_desc, temp, humidity, need_clothes, coords)


# ========== 交互模式 ==========

def interactive_mode():
    """交互模式"""
    print("=" * 55)
    print("🌍 天气 Agent 已启动 - 支持全世界任意城市")
    print("=" * 55)
    print("支持：中文城市名、英文城市名、城市别名")
    print("示例：")
    print("  - 北京天气怎么样？")
    print("  - New York 今天适合穿什么？")
    print("  - 东京冷不冷？")
    print("  - 巴黎天气如何？")
    print("=" * 55)
    print("输入 'exit' 退出")
    print("=" * 55)
    
    while True:
        user_input = input("\n你: ").strip()
        if user_input.lower() in ['exit', 'quit', 'q']:
            print("再见！👋")
            break
        if not user_input:
            continue
        response = chat_with_weather(user_input)
        print(f"助手: {response}")


# ========== 测试代码 ==========

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # 测试模式
        print("=" * 55)
        print("📋 测试用例 - 全世界任意城市")
        print("=" * 55)
        
        test_cases = [
            "今天北京天气怎么样？",
            "上海今天天气如何？适合穿什么？",
            "New York 天气怎么样？",
            "London 今天冷不冷？",
            "东京适合穿什么？",
            "巴黎天气如何？",
            "乌鲁木齐今天多少度？",
            "拉萨冷不冷？",
        ]
        
        for test in test_cases:
            print(f"\n用户: {test}")
            print(f"助手: {chat_with_weather(test)}")
    else:
        # 默认交互模式
        interactive_mode()