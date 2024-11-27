import os
import json
import csv
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from openai import OpenAI
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv
import logging

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)  # 세션을 위한 시크릿 키 설정
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# 다이어트 관련 설문 문항들
all_questions = [
    "식사 시간이 불규칙한 편인가요?",
    "스트레스를 받으면 과식하는 경향이 있나요?",
    "운동할 때 즐거움을 느끼시나요?",
    "식사 계획을 세우는 것이 어렵게 느껴지시나요?",
    "야식을 자주 먹는 편인가요?",
    "체중 감량에 실패한 경험이 많으신가요?",
    "식사를 빨리 하는 편인가요?",
    "다이어트 중에 주변의 지지를 받고 계신가요?",
    "음식을 통해 감정을 달래는 경향이 있나요?",
    "규칙적인 운동 습관을 유지하기 어려우신가요?",
    "식사량을 조절하는 것이 어렵나요?",
    "체중 증가에 대한 불안감이 있으신가요?",
    "식사를 거르는 경우가 자주 있나요?",
    "다이어트에 대한 부정적인 경험이 있나요?",
    "식사 후 죄책감을 느끼시나요?"
]

# 각 질문에 대한 선택지
all_choices = [["전혀 아니다", "아니다", "보통이다", "그렇다", "매우 그렇다"]] * len(all_questions)

# 설문 카테고리와 문항 정의
survey_categories = {
    'habits': {
        'title': '식습관 및 활동',
        'questions': [
            {
                'text': '식사 시간이 불규칙한 편인가요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '스트레스를 받으면 음식으로 해소하는 편인가요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '운동하는 것을 즐기시나요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '야식을 자주 먹는 편인가요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '하루 식사 횟수가 일정한가요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '현재 식습관에서 가장 개선하고 싶은 점은 무엇인가요?',
                'type': 'text'
            }
        ]
    },
    'ideal_body': {
        'title': '나의 이상적인 몸매',
        'questions': [
            {
                'text': '마른 체형이 이상적이라고 생각하시나요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '근육질의 몸매가 좋다고 생각하시나요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '현재 체형에 만족하시나요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '체중보다 체형이 더 중요하다고 생각하시나요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '다이어트의 목표가 미용 목적인가요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '당신이 생각하는 이상적인 체형을 자세히 설명해주세요.',
                'type': 'text'
            },
            {
                'text': '고객님이 목표로하는 체중이 몇 kg인지 알려주세요.',
                'type': 'text'
            }
        ]
    },
    'diet_tendency': {
        'title': '나의 다이어트 성향',
        'questions': [
            {
                'text': '다이어트 실패 경험이 많은 편인가요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '체중 변화에 민감한 편인가요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '다이어트를 시작하면 스트레스를 많이 받나요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '주변 사람들의 체형 변화에 관심이 많은가요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '다이어트 정보를 자주 찾아보시나요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '지금까지 시도해본 다이어트 방법들과 그 결과에 대해 설명해주세요.',
                'type': 'text'
            }
        ]
    }
}

# 설문 문항 로드
def load_survey_questions():
    return all_questions

# CSV 파일에 결과 저장
def save_to_csv(user_name, survey_date, survey_data, analysis_result):
    csv_file = f'data/{user_name}_{survey_date}_survey.csv'
    file_exists = os.path.isfile(csv_file)
    
    # 결과를 1차원 데이터로 변환
    flat_data = {
        'name': user_name,
        'date': survey_date,
    }
    
    # 설문 응답 추가
    for question_id, answer in survey_data.items():
        flat_data[f'{question_id}_answer'] = answer  # Adjusted based on data structure
    
    # 분석 결과 추가
    for section_name in ['personality', 'psychological_state', 'current_status', 'potential_risks', 'treatment_scores', 'overall_analysis']:
        section_data = getattr(analysis_result, section_name, None)
        if section_data:
            flat_data[f'{section_name}_title'] = section_data.title
            flat_data[f'{section_name}_description'] = section_data.description
            
            # Handle lists within section_data
            if section_name == 'treatment_scores':
                flat_data[f'{section_name}_procedural_necessity'] = section_data.procedural_necessity
                flat_data[f'{section_name}_surgical_necessity'] = section_data.surgical_necessity
            else:
                for attr_name in ['traits', 'key_points', 'strengths', 'challenges', 'risk_factors', 'recommendations']:
                    attr_value = getattr(section_data, attr_name, None)
                    if attr_value:
                        for i, item in enumerate(attr_value):
                            flat_data[f'{section_name}_{attr_name}_{i+1}'] = item
    
    # CSV 파일에 저장
    with open(csv_file, 'a', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(flat_data.keys()))
        
        # 파일이 새로 생성된 경우 헤더 작성
        if not file_exists:
            writer.writeheader()
        
        writer.writerow(flat_data)
    logging.info(f"Data saved to {csv_file} successfully.")

# Pydantic models for structured output
class Trait(BaseModel):
    title: str
    description: str
    traits: List[str]

class PsychologicalState(BaseModel):
    title: str
    description: str
    key_points: List[str]

class CurrentStatus(BaseModel):
    title: str
    description: str
    strengths: List[str]
    challenges: List[str]

class PotentialRisks(BaseModel):
    title: str
    description: str
    risk_factors: List[str]
    recommendations: List[str]

class Treatment_Scores(BaseModel):
    title: str
    description: str
    procedural_necessity: int
    surgical_necessity: int

class OverallAnalysis(BaseModel):
    title: str
    description: str
    overall_analysis: str

class AnalysisResult(BaseModel):
    personality: Trait
    psychological_state: PsychologicalState
    current_status: CurrentStatus
    potential_risks: PotentialRisks
    treatment_scores: Treatment_Scores
    overall_analysis: OverallAnalysis

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['GET'])
def start():
    # Clear all previous session data
    session.clear()
    return render_template('landing.html')

@app.route('/category_select')
def category_select():
    if 'user_name' not in session:
        return redirect(url_for('start'))
    completed_categories = session.get('completed_categories', [])
    return render_template('category_select.html', 
                         survey_categories=survey_categories,
                         completed_categories=completed_categories)

@app.route('/survey', methods=['GET', 'POST'])
def survey():
    if request.method == 'POST':
        name = request.form.get('name')
        date = request.form.get('date')
        age = request.form.get('age')
        gender = request.form.get('gender')
        height = request.form.get('height')
        weight = request.form.get('weight')
        
        session['user_info'] = {
            'name': name,
            'date': date,
            'age': age,
            'gender': gender,
            'height': height,
            'weight': weight
        }
        session['user_name'] = name
        session['survey_date'] = date
        return redirect(url_for('category_select'))
    
    if 'user_name' not in session:
        return redirect(url_for('start'))
    
    category = request.args.get('category')
    if not category or category not in survey_categories:
        return redirect(url_for('category_select'))
    
    return render_template('survey.html', 
                         category=category,
                         questions=survey_categories[category]['questions'],
                         category_title=survey_categories[category]['title'])

@app.route('/save_category', methods=['POST'])
def save_category():
    if 'user_name' not in session:
        return jsonify({"error": "로그인이 필요합니다."}), 401

    try:
        data = request.get_json()
        category = data.get('category')
        responses = data.get('responses')

        if not category or not responses:
            return jsonify({"error": "카테고리와 응답이 필요합니다."}), 400

        # Initialize survey_responses in session if not exists
        if 'survey_responses' not in session:
            session['survey_responses'] = {}
        
        # Initialize completed_categories if not exists
        if 'completed_categories' not in session:
            session['completed_categories'] = []

        # Save responses for the category
        session['survey_responses'][category] = responses
        
        # Mark category as completed if not already marked
        if category not in session['completed_categories']:
            session['completed_categories'].append(category)
        
        session.modified = True

        return jsonify({"status": "success"})

    except Exception as e:
        print(f"Error saving category: {str(e)}")
        return jsonify({"error": "응답 저장 중 오류가 발생했습니다."}), 500

@app.route('/analyze_survey', methods=['GET', 'POST'])
def analyze_survey():
    if 'user_name' not in session:
        return redirect(url_for('start'))

    if 'survey_responses' not in session:
        return jsonify({"error": "설문 응답이 없습니다."}), 400

    try:
        data = session['survey_responses']
        user_info = session.get('user_info', {})

        # Build the analysis prompt
        analysis_prompt = f"""
        사용자 정보:
        - 나이: {user_info.get('age')}세
        - 성별: {'남성' if user_info.get('gender') == 'male' else '여성'}
        - 키: {user_info.get('height')}cm
        - 체중: {user_info.get('weight')}kg

        설문 응답:
        """
        for category, responses in data.items():
            category_title = survey_categories[category]['title']
            analysis_prompt += f"\n[{category_title}]\n"
            for response in responses:
                analysis_prompt += f"Q: {response['question']}\nA: {response['answer']}\n"

        analysis_prompt += """
        위 응답을 바탕으로 사용자의 다이어트 성향을 분석해주세요.
        1. 식습관, 이상적인 몸매에 대한 생각, 그리고 다이어트 성향을 종합적으로 고려하여
        personality, psychological_state, current_status, potential_risks, treatment_scores, overall_analysis 항목으로 구분하여 분석해주세요.
        2. treatment_scores의 경우, 0~100의 정수를 사용해야합니다.
        3. 상담자의 답변을 봤을 때, 상담자가 매우 건강한 상태가 아니라면, 가급적이면 시술 필요도와 수술 필요도를 높게 설정하세요.
        overall_analysis에서는 treatment_scores에 대한 분석을 반드시 포함해야합니다.
        4. 말투의 경우, '고객님'을 주어로 사용하고, 친절하고 부드럽게 작성하세요.
        5. 다시 한 번 강조하지만, 모든 응답은 반드시 한국어로 작성해야합니다.
        6. 말투의 경우, '고객님'을 주어로 사용하고, 친절하고 부드럽게 작성하세요.

        이제 시작하세요.
        """

        completion = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "당신은 전문 다이어트 심리 상담가입니다."},
                {"role": "user", "content": analysis_prompt}
            ],
            response_format=AnalysisResult
        )

        # Correct refusal check
        if completion.choices[0].message.refusal:
            return jsonify({"error": "분석을 수행할 수 없습니다. 다시 시도해주세요."}), 400

        result = completion.choices[0].message.parsed

        print(result)

        # Save results to CSV
        if 'user_name' in session and 'survey_date' in session:
            save_to_csv(session['user_name'], session['survey_date'], data, result)

        try:
            # Convert Pydantic model to dictionary
            if hasattr(result, 'model_dump'):
                result_dict = {
                    "personality": result.personality.model_dump(),
                    "psychological_state": result.psychological_state.model_dump(),
                    "current_status": result.current_status.model_dump(),
                    "potential_risks": result.potential_risks.model_dump(),
                    "treatment_scores": result.treatment_scores.model_dump(),
                    "overall_analysis": result.overall_analysis.model_dump()
                }
            else:
                result_dict = {
                    "personality": result.personality.dict(),
                    "psychological_state": result.psychological_state.dict(),
                    "current_status": result.current_status.dict(),
                    "potential_risks": result.potential_risks.dict(),
                    "treatment_scores": result.treatment_scores.dict(),
                    "overall_analysis": result.overall_analysis.dict()
                }
            
            # Store the result in session
            session['analysis_result'] = result_dict
            return redirect(url_for('show_result'))

        except Exception as json_error:
            print(f"JSON Serialization Error: {str(json_error)}")
            return jsonify({"error": "결과 변환 중 오류가 발생했습니다."}), 400

    except Exception as api_error:
        print(f"API Error: {str(api_error)}")
        return jsonify({"error": "AI 분석 중 오류가 발생했습니다. 다시 시도해주세요."}), 500

@app.route('/result')
def show_result():
    if 'user_name' not in session or 'analysis_result' not in session:
        return redirect(url_for('category_select'))
    return render_template('result.html', analysis_result=session.get('analysis_result'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

# For Vercel Serverless Function
app = app
