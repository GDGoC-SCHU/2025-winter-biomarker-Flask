from flask import Flask, request, jsonify
import json
import google.generativeai as genai
import pandas as pd
from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

# 환경 변수에서 API 키 가져오기
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = Flask(__name__)

# Google Gemini API 설정
genai.configure(api_key=GEMINI_API_KEY)

# 환경 변수에서 CSV 파일 경로 불러오기
csv_path = os.getenv("CSV_PATH")

# 음식 데이터 로드
df = pd.read_csv(csv_path)

def filter_foods_based_on_goal(user_info, food_data, goal, gender):
    protein_calculation = user_info['weight'] * 1.6  
    fat_calculation = user_info['weight'] * 1
    
    if goal == 'diet':
        food_data = food_data.sort_values(by=['식이섬유(g)'], ascending=False)
        food_data = food_data[(food_data['당류(g)'] <= 20) & (food_data['나트륨(mg)'] <= 2000) & (food_data['에너지(kcal)'] <= (user_info['bmr'] * 0.8))]
    elif goal == 'muscle_gain':
        if gender == 'man':
            protein_calculation = user_info['weight'] * 2.0
        else:
            protein_calculation = user_info['weight'] * 1.5
        food_data = food_data.sort_values(by=['단백질(g)'], ascending=False)
        food_data = food_data[(food_data['단백질(g)'] >= protein_calculation) & (food_data['지방(g)'] <= fat_calculation)]
    elif goal == 'maintain':
        food_data = food_data.sort_values(by=['단백질(g)'], ascending=False)
        food_data = food_data[(food_data['단백질(g)'] >= user_info['weight'] * 1.0) & (food_data['나트륨(mg)'] <= 2000)]
    elif goal == 'bulk':
        if gender == 'woman':
            protein_calculation = user_info['weight'] * 2.0
        else:
            protein_calculation = user_info['weight'] * 1.5
        food_data = food_data.sort_values(by=['단백질(g)', '에너지(kcal)'], ascending=False)
        food_data = food_data[(food_data['단백질(g)'] >= protein_calculation) & (food_data['에너지(kcal)'] <= (user_info['bmr'] * 1.2))]
    return food_data

def get_recommended_food(user_info):
    food_data = df[~df["식품대분류명"].str.contains("빵 및 과자|음료 및 차류|유제품류 및 빙과류", na=False)]
    food_data = filter_foods_based_on_goal(user_info, food_data, user_info['goal'], user_info['gender'])
    if food_data.empty:
        return []
    return food_data.sample(n=min(3, len(food_data))).to_dict(orient="records")

def generate_diet_plan_from_data(user_info):
    # "bmr"을 "basal metabolic rate"로 변경
    user_info["basal metabolic rate"] = user_info.pop("bmr")
    print(user_info)
    
    recommended_foods = get_recommended_food(user_info)
    if recommended_foods:
        foods_text = f"추천 음식 리스트:\n{recommended_foods}"
    else:
        foods_text = "user_info를 가지고, ai 추천 식단을 만들어줘"
    
    prompt = f"""
    사용자의 신체 정보: {user_info}
    {foods_text}
    이 정보를 바탕으로 목표에 따른 하루에 먹어야할 영양소 정보와 비율을 알려주고,
    하루 식단을 아침, 점심, 저녁으로 나눠서 적어주고 추천 운동 방법을 알려줘.

    아래 형식(JSON)으로 응답을 작성해줘:

    {{
        "result": "목표: (목표 입력) 에너지: (kcal 값) 단백질: (g 값) 지방: (g 값) 탄수화물: (g 값)",
        "recommend-meal": {{
            "breakfast": "(아침 식단 및 kcal 값)",
            "lunch": "(점심 식단 및 kcal 값)",
            "dinner": "(저녁 식단 및 kcal 값)"
        }},
        "recommend-exercise": "(추천 운동 방법 상세 설명)"
    }}

    위 JSON 형식에 맞춰 정확하게 응답해줘.
    """
    
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(prompt)

    structured_response = json.loads(response.text)  # Gemini 응답을 JSON으로 변환

    return structured_response

@app.route('/<int:userId>/recommend_meal', methods=['POST'])
def recommend_meal(userId):
    user_info = request.json
    diet_plan = generate_diet_plan_from_data(user_info)
    
    # 스프링 서버로 반환할 JSON 데이터 생성
    response_data = {"answer": diet_plan}
    
    return app.response_class(
        response=json.dumps(response_data, ensure_ascii=False),  # UTF-8 유지
        status=200,
        mimetype='application/json'
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
