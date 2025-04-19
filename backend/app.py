from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from openai import OpenAI
import boto3
import json
import logging

# 加載環境變量
load_dotenv()

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化Flask應用
app = Flask(__name__)
CORS(app)  # 允許跨域請求

# 初始化OpenAI客戶端
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.openai.com/v1"  # 使用默認API端點
)


def create_aws_client():
    """創建AWS Price List API客戶端"""
    return boto3.client(
        'pricing',
        region_name='us-east-1',  # Price List API 僅在us-east-1和ap-south-1可用
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )


def extract_parameters_with_openai(query):
    """使用OpenAI API提取查詢參數"""
    logger.info(f"從查詢中提取參數: {query}")

    try:
        # 使用OpenAI函數調用功能提取參數
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "你是一個專門解析AWS價格查詢的助手。提取關鍵參數如服務類型、地區、實例類型等。"},
                {"role": "user", "content": query}
            ],
            tools=[{
                "type": "function",
                "function": {
                    "name": "get_aws_price",
                    "description": "獲取AWS服務的價格信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service": {
                                "type": "string",
                                "description": "AWS服務類型，如EC2、S3、RDS等"
                            },
                            "region": {
                                "type": "string",
                                "description": "AWS區域，如us-east-1、ap-northeast-1(東京)等"
                            },
                            "instance_type": {
                                "type": "string",
                                "description": "實例類型，如t2.micro、m5.large等"
                            },
                            "os": {
                                "type": "string",
                                "description": "操作系統，如Linux、Windows等"
                            }
                        },
                        "required": ["service"]
                    }
                }
            }],
            tool_choice={"type": "function",
                         "function": {"name": "get_aws_price"}}
        )

        # 從回應中提取函數參數
        tool_call = response.choices[0].message.tool_calls[0]
        function_args = json.loads(tool_call.function.arguments)
        return function_args

    except Exception as e:
        logger.error(f"OpenAI API調用錯誤: {str(e)}")
        return {"error": str(e)}


def query_aws_price(params):
    """查詢AWS價格"""
    logger.info(f"查詢AWS價格使用參數: {params}")

    try:
        client = create_aws_client()

        # 目前僅實現EC2價格查詢，可以根據需要擴展到其他服務
        if params.get('service', '').lower() == 'ec2':
            filters = []

            # 添加實例類型過濾器
            if 'instance_type' in params:
                filters.append({
                    'Type': 'TERM_MATCH',
                    'Field': 'instanceType',
                    'Value': params['instance_type']
                })

            # 添加區域過濾器
            if 'region' in params:
                # 如果是東京，轉換為對應的區域代碼
                if params['region'].lower() == '東京' or '東京' in params['region'].lower():
                    region_code = 'ap-northeast-1'
                else:
                    region_code = params['region']

                filters.append({
                    'Type': 'TERM_MATCH',
                    'Field': 'location',
                    'Value': region_code
                })

            # 添加操作系統過濾器
            if 'os' in params:
                os_value = params['os'].lower()
                if 'linux' in os_value:
                    os_term = 'Linux'
                elif 'windows' in os_value:
                    os_term = 'Windows'
                else:
                    os_term = params['os']

                filters.append({
                    'Type': 'TERM_MATCH',
                    'Field': 'operatingSystem',
                    'Value': os_term
                })

            # 添加其他必要的過濾器
            filters.append({
                'Type': 'TERM_MATCH',
                'Field': 'productFamily',
                'Value': 'Compute Instance'
            })

            filters.append({
                'Type': 'TERM_MATCH',
                'Field': 'tenancy',
                'Value': 'Shared'
            })

            # 執行API查詢
            response = client.get_products(
                ServiceCode='AmazonEC2',
                Filters=filters
            )

            # 解析返回的價格數據
            pricing_data = []
            for product_str in response['PriceList']:
                product = json.loads(product_str)

                # 從對象中提取價格信息
                instance_details = product['product']['attributes']
                instance_type = instance_details.get('instanceType', 'N/A')
                os = instance_details.get('operatingSystem', 'N/A')
                region = instance_details.get('location', 'N/A')

                # 提取價格
                on_demand_price = None
                try:
                    terms = product.get('terms', {}).get('OnDemand', {})
                    if terms:
                        price_dimensions = next(iter(terms.values()))[
                            'priceDimensions']
                        price_info = next(iter(price_dimensions.values()))
                        on_demand_price = price_info.get(
                            'pricePerUnit', {}).get('USD', 'N/A')
                except Exception as e:
                    logger.error(f"價格解析錯誤: {str(e)}")

                pricing_data.append({
                    'instanceType': instance_type,
                    'operatingSystem': os,
                    'region': region,
                    'onDemandPrice': on_demand_price,
                    'unit': 'USD per Hour'
                })

            return pricing_data
        else:
            return {"error": f"目前僅支持EC2服務，您請求的是 {params.get('service', 'unknown')}"}

    except Exception as e:
        logger.error(f"AWS價格API調用錯誤: {str(e)}")
        return {"error": str(e)}


def generate_response_with_openai(query, pricing_data):
    """使用OpenAI生成自然語言回應"""
    logger.info(f"生成回應: 查詢={query}, 數據={pricing_data}")

    try:
        if isinstance(pricing_data, dict) and 'error' in pricing_data:
            return f"抱歉，在獲取價格時出現問題: {pricing_data['error']}"

        if not pricing_data:
            return "抱歉，使用提供的參數沒有找到任何價格信息。請嘗試使用不同的參數或更具體的查詢。"

        # 使用OpenAI生成人性化回應
        pricing_str = json.dumps(pricing_data, ensure_ascii=False)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "你是一個AWS成本專家，提供準確的價格信息和建議。"},
                {"role": "user", "content": f"用戶查詢: '{query}'\n\n價格數據: {pricing_str}\n\n請提供簡潔明了的回應，包含用戶請求的價格信息。"}
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"生成回應時發生錯誤: {str(e)}")
        return f"抱歉，在生成回應時遇到問題: {str(e)}"


@app.route('/api/query', methods=['POST'])
def process_query():
    """處理用戶查詢請求"""
    try:
        data = request.json
        query = data.get('query', '')

        if not query:
            return jsonify({"error": "請提供查詢內容"}), 400

        # 1. 使用OpenAI提取參數
        parameters = extract_parameters_with_openai(query)

        # 2. 使用參數查詢AWS價格
        pricing_data = query_aws_price(parameters)

        # 3. 生成自然語言回應
        response_text = generate_response_with_openai(query, pricing_data)

        return jsonify({
            "query": query,
            "parameters": parameters,
            "pricing_data": pricing_data,
            "response": response_text
        })

    except Exception as e:
        logger.error(f"處理查詢時發生錯誤: {str(e)}")
        return jsonify({"error": f"處理查詢時發生錯誤: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
