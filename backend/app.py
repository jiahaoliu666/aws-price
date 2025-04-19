from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import openai
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

# 設置API密鑰
openai.api_key = os.getenv("OPENAI_API_KEY")


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
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "你是一個專門解析AWS價格查詢的助手。提取關鍵參數如服務類型、地區、實例類型等。"},
                {"role": "user", "content": query}
            ],
            functions=[{
                "name": "get_aws_price",
                "description": "獲取AWS服務的價格信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "AWS服務類型，如EC2、S3、RDS、Lambda、DynamoDB等"
                        },
                        "region": {
                            "type": "string",
                            "description": "AWS區域，如us-east-1、ap-northeast-1(東京)等"
                        },
                        "instance_type": {
                            "type": "string",
                            "description": "EC2或RDS實例類型，如t2.micro、m5.large等"
                        },
                        "os": {
                            "type": "string",
                            "description": "EC2操作系統，如Linux、Windows等"
                        },
                        "storage_class": {
                            "type": "string",
                            "description": "S3儲存類型，如Standard(標準)、Intelligent-Tiering(智能分層)、Glacier(冷藏)等"
                        },
                        "storage_size": {
                            "type": "string",
                            "description": "儲存大小，如100GB、1TB等"
                        },
                        "db_engine": {
                            "type": "string",
                            "description": "RDS數據庫引擎，如MySQL、PostgreSQL、Oracle、SQL Server等"
                        }
                    },
                    "required": ["service"]
                }
            }],
            function_call={"name": "get_aws_price"}
        )

        # 從回應中提取函數參數
        function_args = json.loads(
            response.choices[0].message.function_call.arguments)
        return function_args

    except Exception as e:
        logger.error(f"OpenAI API調用錯誤: {str(e)}")
        return {"error": str(e)}


def query_aws_price(params):
    """查詢AWS價格"""
    logger.info(f"查詢AWS價格使用參數: {params}")

    try:
        client = create_aws_client()
        service = params.get('service', '').lower()

        # 獲取區域代碼和名稱
        region_code = None
        region_name = None
        if 'region' in params:
            # 處理區域參數
            if params['region'].lower() == '東京' or '東京' in params['region'].lower():
                region_code = 'ap-northeast-1'
            else:
                region_code = params['region']

            # 區域代碼到AWS Price List API位置名稱的映射
            region_mapping = {
                'us-east-1': 'US East (N. Virginia)',
                'us-east-2': 'US East (Ohio)',
                'us-west-1': 'US West (N. California)',
                'us-west-2': 'US West (Oregon)',
                'ap-east-1': 'Asia Pacific (Hong Kong)',
                'ap-south-1': 'Asia Pacific (Mumbai)',
                'ap-northeast-1': 'Asia Pacific (Tokyo)',
                'ap-northeast-2': 'Asia Pacific (Seoul)',
                'ap-northeast-3': 'Asia Pacific (Osaka)',
                'ap-southeast-1': 'Asia Pacific (Singapore)',
                'ap-southeast-2': 'Asia Pacific (Sydney)',
                'ca-central-1': 'Canada (Central)',
                'eu-central-1': 'EU (Frankfurt)',
                'eu-west-1': 'EU (Ireland)',
                'eu-west-2': 'EU (London)',
                'eu-west-3': 'EU (Paris)',
                'eu-north-1': 'EU (Stockholm)',
                'sa-east-1': 'South America (Sao Paulo)',
            }
            region_name = region_mapping.get(region_code, region_code)
            logger.info(f"處理區域: 代碼={region_code}, 名稱={region_name}")

        # 處理不同的AWS服務
        if service == 'ec2':
            return query_ec2_price(client, params, region_name)
        elif service == 's3':
            return query_s3_price(client, params, region_name)
        elif service == 'rds':
            return query_rds_price(client, params, region_name)
        elif service == 'lambda':
            return query_lambda_price(client, params, region_name)
        elif service == 'dynamodb':
            return query_dynamodb_price(client, params, region_name)
        else:
            return {"error": f"目前尚未支援 {params.get('service', 'unknown')} 服務的價格查詢"}

    except Exception as e:
        logger.error(f"AWS價格API調用錯誤: {str(e)}")
        return {"error": str(e)}


def query_ec2_price(client, params, region_name):
    """查詢EC2價格"""
    filters = []

    # 添加實例類型過濾器
    if 'instance_type' in params:
        filters.append({
            'Type': 'TERM_MATCH',
            'Field': 'instanceType',
            'Value': params['instance_type']
        })

    # 添加區域過濾器
    if region_name:
        filters.append({
            'Type': 'TERM_MATCH',
            'Field': 'location',
            'Value': region_name
        })
        logger.info(f"使用區域過濾器: {region_name}")

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

    logger.info(f"EC2價格查詢過濾器: {json.dumps(filters)}")

    # 執行API查詢
    response = client.get_products(
        ServiceCode='AmazonEC2',
        Filters=filters
    )

    logger.info(f"API響應PriceList元素數量: {len(response['PriceList'])}")

    # 如果沒有找到結果，嘗試使用更少的過濾器
    if len(response['PriceList']) == 0:
        logger.info("未找到結果，嘗試使用更少的過濾器")
        # 重新構建基本過濾器
        basic_filters = []

        # 只保留實例類型和地區過濾器
        if 'instance_type' in params:
            basic_filters.append({
                'Type': 'TERM_MATCH',
                'Field': 'instanceType',
                'Value': params['instance_type']
            })

        if region_name:
            basic_filters.append({
                'Type': 'TERM_MATCH',
                'Field': 'location',
                'Value': region_name
            })

        try:
            response = client.get_products(
                ServiceCode='AmazonEC2',
                Filters=basic_filters
            )
        except Exception as e:
            logger.error(f"簡化EC2查詢時出錯: {str(e)}")

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
            logger.error(f"EC2價格解析錯誤: {str(e)}")

        pricing_data.append({
            'instanceType': instance_type,
            'operatingSystem': os,
            'region': region,
            'onDemandPrice': on_demand_price,
            'unit': 'USD per Hour'
        })

    return pricing_data


def query_s3_price(client, params, region_name):
    """查詢S3價格"""
    filters = []

    # 添加基本過濾器
    if region_name:
        filters.append({
            'Type': 'TERM_MATCH',
            'Field': 'location',
            'Value': region_name
        })

    # 處理儲存類型 (標準/智能分層/冷藏等)
    storage_class = "Standard"  # 默認值
    if 'storage_class' in params:
        s_class = params['storage_class'].lower()
        if '標準' in s_class or 'standard' in s_class:
            storage_class = "Standard"
        elif '智能' in s_class or 'intelligent' in s_class:
            storage_class = "Intelligent-Tiering"
        elif '冷藏' in s_class or 'glacier' in s_class:
            storage_class = "Glacier"
        elif '深度' in s_class or 'deep' in s_class:
            storage_class = "Glacier Deep Archive"
        elif '單區域' in s_class or 'one zone' in s_class:
            storage_class = "One Zone"
        elif '標準-不頻繁' in s_class or 'infrequent' in s_class:
            storage_class = "Standard - Infrequent Access"

    filters.append({
        'Type': 'TERM_MATCH',
        'Field': 'storageClass',
        'Value': storage_class
    })

    logger.info(f"S3價格查詢過濾器: {json.dumps(filters)}")

    # 執行API查詢
    response = client.get_products(
        ServiceCode='AmazonS3',
        Filters=filters
    )

    logger.info(f"S3 API響應PriceList元素數量: {len(response['PriceList'])}")

    # 解析返回的價格數據
    pricing_data = []
    for product_str in response['PriceList']:
        product = json.loads(product_str)

        # 從對象中提取屬性
        s3_details = product['product']['attributes']
        storage_class = s3_details.get('storageClass', 'N/A')
        volume_type = s3_details.get('volumeType', 'N/A')
        region = s3_details.get('location', 'N/A')

        # 提取價格
        try:
            terms = product.get('terms', {}).get('OnDemand', {})
            if terms:
                for term_key, term_value in terms.items():
                    price_dimensions = term_value.get('priceDimensions', {})
                    for dim_key, dim_value in price_dimensions.items():
                        # 獲取價格單位和描述
                        price = dim_value.get(
                            'pricePerUnit', {}).get('USD', 'N/A')
                        description = dim_value.get('description', '')
                        unit = dim_value.get('unit', '')

                        pricing_data.append({
                            'storageClass': storage_class,
                            'volumeType': volume_type,
                            'region': region,
                            'price': price,
                            'description': description,
                            'unit': unit
                        })
        except Exception as e:
            logger.error(f"S3價格解析錯誤: {str(e)}")

    # 計算特定容量的價格（如果指定了容量）
    if 'storage_size' in params and pricing_data:
        try:
            size_str = params['storage_size']
            # 提取數字和單位 (GB, TB 等)
            import re
            match = re.search(r'(\d+)\s*([a-zA-Z]+)?', size_str)
            if match:
                size = float(match.group(1))
                unit = match.group(2).upper() if match.group(2) else 'GB'

                # 轉換為GB (AWS S3定價通常以GB為單位)
                if unit == 'TB':
                    size *= 1024
                elif unit == 'MB':
                    size /= 1024

                # 添加總價計算
                for item in pricing_data:
                    if 'GB-Month' in item.get('unit', ''):
                        item['estimatedCost'] = float(
                            item['price']) * size if item['price'] != 'N/A' else 'N/A'
                        item['estimatedCostUnit'] = 'USD per Month'
        except Exception as e:
            logger.error(f"計算S3存儲總價時出錯: {str(e)}")

    return pricing_data


def query_rds_price(client, params, region_name):
    """查詢RDS價格"""
    filters = []

    # 添加基本過濾器
    if region_name:
        filters.append({
            'Type': 'TERM_MATCH',
            'Field': 'location',
            'Value': region_name
        })

    # 處理數據庫引擎
    if 'db_engine' in params:
        engine = params['db_engine'].lower()
        db_engine = "MySQL"  # 默認值

        if 'mysql' in engine:
            db_engine = "MySQL"
        elif 'postgresql' in engine or 'postgres' in engine:
            db_engine = "PostgreSQL"
        elif 'oracle' in engine:
            db_engine = "Oracle"
        elif 'sqlserver' in engine or 'sql server' in engine:
            db_engine = "SQL Server"
        elif 'aurora' in engine:
            db_engine = "Aurora "
            if 'mysql' in engine:
                db_engine += "MySQL"
            elif 'postgresql' in engine:
                db_engine += "PostgreSQL"
        elif 'mariadb' in engine:
            db_engine = "MariaDB"

        filters.append({
            'Type': 'TERM_MATCH',
            'Field': 'databaseEngine',
            'Value': db_engine
        })

    # 處理實例類型
    if 'instance_type' in params:
        filters.append({
            'Type': 'TERM_MATCH',
            'Field': 'instanceType',
            'Value': params['instance_type']
        })

    logger.info(f"RDS價格查詢過濾器: {json.dumps(filters)}")

    # 執行API查詢
    response = client.get_products(
        ServiceCode='AmazonRDS',
        Filters=filters
    )

    logger.info(f"RDS API響應PriceList元素數量: {len(response['PriceList'])}")

    # 解析返回的價格數據
    pricing_data = []
    for product_str in response['PriceList']:
        product = json.loads(product_str)

        # 從對象中提取屬性
        rds_details = product['product']['attributes']
        db_engine = rds_details.get('databaseEngine', 'N/A')
        instance_type = rds_details.get('instanceType', 'N/A')
        deployment_option = rds_details.get('deploymentOption', 'N/A')
        region = rds_details.get('location', 'N/A')

        # 提取價格
        try:
            terms = product.get('terms', {}).get('OnDemand', {})
            if terms:
                for term_key, term_value in terms.items():
                    price_dimensions = term_value.get('priceDimensions', {})
                    for dim_key, dim_value in price_dimensions.items():
                        price = dim_value.get(
                            'pricePerUnit', {}).get('USD', 'N/A')
                        description = dim_value.get('description', '')
                        unit = dim_value.get('unit', '')

                        pricing_data.append({
                            'databaseEngine': db_engine,
                            'instanceType': instance_type,
                            'deploymentOption': deployment_option,
                            'region': region,
                            'price': price,
                            'description': description,
                            'unit': unit
                        })
        except Exception as e:
            logger.error(f"RDS價格解析錯誤: {str(e)}")

    return pricing_data


def query_lambda_price(client, params, region_name):
    """查詢Lambda價格"""
    filters = []

    # 添加基本過濾器
    if region_name:
        filters.append({
            'Type': 'TERM_MATCH',
            'Field': 'location',
            'Value': region_name
        })

    logger.info(f"Lambda價格查詢過濾器: {json.dumps(filters)}")

    # 執行API查詢
    response = client.get_products(
        ServiceCode='AWSLambda',
        Filters=filters
    )

    logger.info(f"Lambda API響應PriceList元素數量: {len(response['PriceList'])}")

    # 解析返回的價格數據
    pricing_data = []
    for product_str in response['PriceList']:
        product = json.loads(product_str)

        # 從對象中提取屬性
        lambda_details = product['product']['attributes']
        region = lambda_details.get('location', 'N/A')
        group = lambda_details.get('group', 'N/A')

        # 提取價格
        try:
            terms = product.get('terms', {}).get('OnDemand', {})
            if terms:
                for term_key, term_value in terms.items():
                    price_dimensions = term_value.get('priceDimensions', {})
                    for dim_key, dim_value in price_dimensions.items():
                        price = dim_value.get(
                            'pricePerUnit', {}).get('USD', 'N/A')
                        description = dim_value.get('description', '')
                        unit = dim_value.get('unit', '')

                        pricing_data.append({
                            'group': group,
                            'region': region,
                            'price': price,
                            'description': description,
                            'unit': unit
                        })
        except Exception as e:
            logger.error(f"Lambda價格解析錯誤: {str(e)}")

    return pricing_data


def query_dynamodb_price(client, params, region_name):
    """查詢DynamoDB價格"""
    filters = []

    # 添加基本過濾器
    if region_name:
        filters.append({
            'Type': 'TERM_MATCH',
            'Field': 'location',
            'Value': region_name
        })

    logger.info(f"DynamoDB價格查詢過濾器: {json.dumps(filters)}")

    # 執行API查詢
    response = client.get_products(
        ServiceCode='AmazonDynamoDB',
        Filters=filters
    )

    logger.info(f"DynamoDB API響應PriceList元素數量: {len(response['PriceList'])}")

    # 解析返回的價格數據
    pricing_data = []
    for product_str in response['PriceList']:
        product = json.loads(product_str)

        # 從對象中提取屬性
        dynamodb_details = product['product']['attributes']
        region = dynamodb_details.get('location', 'N/A')
        group = dynamodb_details.get('group', 'N/A')

        # 提取價格
        try:
            terms = product.get('terms', {}).get('OnDemand', {})
            if terms:
                for term_key, term_value in terms.items():
                    price_dimensions = term_value.get('priceDimensions', {})
                    for dim_key, dim_value in price_dimensions.items():
                        price = dim_value.get(
                            'pricePerUnit', {}).get('USD', 'N/A')
                        description = dim_value.get('description', '')
                        unit = dim_value.get('unit', '')

                        pricing_data.append({
                            'group': group,
                            'region': region,
                            'price': price,
                            'description': description,
                            'unit': unit
                        })
        except Exception as e:
            logger.error(f"DynamoDB價格解析錯誤: {str(e)}")

    return pricing_data


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
        response = openai.chat.completions.create(
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
    port = int(os.getenv('BACKEND_PORT', 3001))
    app.run(debug=True, host='0.0.0.0', port=port)
