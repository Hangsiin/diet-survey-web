import os
import json
import csv
import xlsxwriter
from io import BytesIO
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from openai import OpenAI
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv
import logging

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)  # 세션을 위한 시크릿 키 설정
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# 설문 카테고리와 문항 정의
survey_categories = {
    'habits': {
        'title': '식습관 및 활동',
        'questions': [
            # 식습관 & 활동
            {
                'text': '하루에 식사를 몇 끼 정도 하시나요?',
                'choices': ['하루 1끼', '하루 2끼', '하루 3끼', '4끼 이상', '불규칙하다']
            },
            {
                'text': '평소 식사를 주로 어떤 방식으로 하시나요?',
                'choices': [
                    '집에서 직접 만들어 먹는다',
                    '배달 음식 또는 포장 음식을 먹는다',
                    '외식을 주로 한다',
                    '간단히 간편식을 먹는다(예: 샌드위치, 컵라면 등)'
                ]
            },
            {
                'text': '식사량은 보통 어느 정도인가요?',
                'choices': [
                    '항상 과식하는 편이다',
                    '적당히 배부를 정도로 먹는다',
                    '소식하거나 부족하게 먹는다',
                    '식사량이 일정하지 않다'
                ]
            },
            {
                'text': '주로 어떤 종류의 음식을 자주 드시나요?',
                'choices': [
                    '탄수화물 위주의 식사(밥, 빵, 면 등)',
                    '고기나 생선 중심의 단백질 식사',
                    '채소나 샐러드 중심의 식사',
                    '간편식이나 가공식품(인스턴트, 패스트푸드 등)',
                    '달콤하거나 기름진 간식을 자주 먹는다'
                ],
                'type': 'checkbox'
            },
            {
                'text': '다이어트 식단이 힘든이유가 무엇인가요?',
                'type': 'text'
            },
            # 활동
            {
                'text': '운동하는 것을 즐기시나요?',
                'choices': ['매우 그렇다', '그렇다', '보통이다', '아니다', '전혀 아니다']
            },
            {
                'text': '운동의 필요성을 못느끼는 부분은 어떤것일까요?',
                'choices': [
                    '흥미가 없어서',
                    '시간이 없어서',
                    '체력이 없어서 또는 피곤해서',
                    '아직 건강하기 때문에',
                    '구지 내몸을 힘들게 하고 싶지 않아서'
                ]
            },
            {
                'text': '운동의 필요성을 느낀다면 어느부분 때문일까요?',
                'choices': [
                    '건강',
                    '외모',
                    '체력',
                    '지식',
                    '많이먹기 위해서'
                ]
            },
            {
                'text': '본인이 제일 선호하는 운동은?',
                'choices': [
                    '유산소 (걷기)',
                    '스트레칭 (간단한 움직임, 몸풀기)',
                    '근력 (헬스, 웨이트)',
                    '필라테스, 요가',
                    '기타'
                ]
            },
            {
                'text': '운동할 때 어떤 부분이 제일 힘든가요?',
                'choices': [
                    '매일 해야 하는부분 때문에',
                    '힘들어서',
                    '혼자서 할때',
                    '운동을 하고 나면 근육통이 너무 심해서',
                    '눈에 띄는 변화가 없어서'
                ]
            },
        ]
    },
    'ideal_body': {
        'title': '나의 이상적인 몸매',
        'questions': [
            {
                'text': '현재 몸에서 가장 변화시키고 싶은 부위는 어디인가요?',
                'choices': ['복부', '허벅지', '팔뚝', '엉덩이', '전체적으로 체형을 개선하고 싶다']
            },
            {
                'text': '몸매 관리에서 가장 중점적으로 원하는 결과는 무엇인가요?',
                'choices': ['군살 제거', '근육량 증가', '체지방 감소', '체형 교정']
            },
            {
                'text': '운동을 통해 만들고 싶은 몸매는 어떤 스타일인가요?',
                'choices': [
                    '날씬하고 가늘게 보이는 몸매',
                    '글래머러스하고 볼륨감 있는 몸매',
                    '복근이 드러나는 강한 인상',
                    '유연하고 균형 잡힌 몸매'
                ]
            },
            {
                'text': '몸매 관리를 통해 얻고 싶은 가장 큰 변화는 무엇인가요?',
                'choices': [
                    '옷이 잘 어울리는 체형',
                    '체중계 숫자의 감소',
                    '활동적인 라이프스타일에 적합한 몸매',
                    '스스로 자존감을 높일 수 있는 몸매'
                ]
            },
            {
                'text': '자신의 체형과 관련해 가장 스트레스를 받는 부분은 무엇인가요?',
                'choices': [
                    '특정 부위의 군살',
                    '전반적으로 균형이 맞지 않는 체형',
                    '근육 부족으로 탄탄하지 않음',
                    '기타'
                ],
                'type': 'checkbox'
            },
            {
                'text': '이상적인 몸매를 유지하기 위해 어느 정도의 노력을 하실 수 있나요?',
                'choices': [
                    '매일 꾸준한 운동 가능',
                    '주 3~4회 운동 가능',
                    '시간 여유에 따라 탄력적으로 가능',
                    '운동보다는 식단 위주로 관리하고 싶다'
                ]
            },
        ]
    },
    'diet_tendency': {
        'title': '나의 다이어트 성향',
        'questions': [
            {
                'text': '과거에 다이어트를 시도한 경험이 있으신가요? 있다면 어떤 방법을 사용하셨나요?',
                'choices': [
                    '식단 조절',
                    '운동',
                    '약물(보조제 포함)',
                    '수술(예: 지방 흡입)',
                    '기타'
                ],
                'type': 'checkbox'
            },
            {
                'text': '다이어트를 진행하면서 가장 어려웠던 점은 무엇인가요?',
                'choices': [
                    '꾸준한 실천',
                    '시간 부족',
                    '식단 유지',
                    '외식 또는 회식 등 환경적 요인',
                    '기타'
                ],
                'type': 'checkbox'
            },
            {
                'text': '다이어트 실패 원인으로 가장 크게 작용한 요소는 무엇이라고 생각하시나요?',
                'choices': [
                    '의지 부족',
                    '잘못된 다이어트 방법',
                    '전문가의 부재',
                    '주변 환경(가족, 직장 등)',
                    '기타'
                ],
                'type': 'checkbox'
            },
            {
                'text': '평소에 식습관이나 생활 패턴에서 다이어트를 방해하는 요인은 무엇인가요?',
                'choices': [
                    '불규칙한 식사',
                    '스트레스성 폭식',
                    '잦은 외식 및 회식',
                    '야식 습관',
                    '기타'
                ],
                'type': 'checkbox'
            },
            {
                'text': '현재 체중 관리 목표를 이루는 데 가장 필요한 지원은 무엇이라고 생각하시나요?',
                'choices': [
                    '맞춤형 식단 제공',
                    '체계적인 운동 코칭',
                    '지속적인 동기부여와 상담',
                    '전문 의료 지원',
                    '기타'
                ]
            },
            {
                'text': '체중 관리 프로그램을 선택할 때 가장 중요하게 생각하는 요소는 무엇인가요?',
                'choices': [
                    '효과',
                    '비용',
                    '편리성(시간 및 거리)',
                    '전문성'
                ]
            },
            {
                'text': '체중 관리 서비스를 이용하기 위해 한 달에 지출할 수 있는 금액은 어느 정도인가요?',
                'choices': [
                    '30만원 이하',
                    '100만원 이상',
                    '300만원 이하',
                    '비용상관없음'
                ]
            },
            {
                'text': '과거에 유료 체중 관리 서비스를 이용해 본 경험이 있다면, 그 비용은 어느 정도였나요?',
                'choices': [
                    '10만원 이하',
                    '100만원 이상',
                    '300만원 이하',
                    '1000만원 이상',
                    '이용한 적 없음'
                ],
                'type': 'radio'
            },
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
    
    # 세션에서 completed_categories 가져오기
    completed_categories = session.get('completed_categories', [])
    
    return render_template('survey.html', 
                           category=category,
                           questions=survey_categories[category]['questions'],
                           category_title=survey_categories[category]['title'],
                           completed_categories=completed_categories)


@app.route('/save_category', methods=['POST'])
def save_category():
    try:
        data = request.get_json()
        category = data.get('category')
        responses = data.get('responses')
        
        if not category or not responses:
            return jsonify({'status': 'error', 'error': 'Missing data'}), 400
        
        # Initialize completed_categories in session if it doesn't exist
        if 'completed_categories' not in session:
            session['completed_categories'] = []
            
        # Add the current category to completed_categories if not already present
        if category not in session['completed_categories']:
            completed_categories = session['completed_categories']
            completed_categories.append(category)
            session['completed_categories'] = completed_categories
            
        # Store responses in session
        if 'survey_responses' not in session:
            session['survey_responses'] = {}
        
        session['survey_responses'][category] = responses
        
        # If all categories are completed, prepare for analysis
        all_categories = ['habits', 'ideal_body', 'diet_tendency']
        if all(cat in session['completed_categories'] for cat in all_categories):
            session['ready_for_analysis'] = True
        
        return jsonify({'status': 'success'})
    except Exception as e:
        logging.error(f"Error in save_category: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

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
        4. overall_analysis에서는 treatment_scores에 대한 분석을 반드시 포함해야합니다.
        5. 말투의 경우, '고객님'을 주어로 사용하고, 친절하고 부드럽게 작성하세요.
        6. 다시 한 번 강조하지만, 모든 응답은 반드시 한국어로 작성해야합니다.

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

@app.route('/download_survey')
def download_survey():
    if 'survey_responses' not in session:
        return redirect(url_for('index'))
    
    # Get user info for filename
    user_info = session.get('user_info', {})
    client_name = user_info.get('name', '무명')
    survey_date = user_info.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    # Create filename
    filename = f'설문결과_{client_name}_{survey_date}.xlsx'
    
    # Create an Excel file in memory
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()
    
    # Add formats
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#E6E6FA',
        'border': 1
    })
    
    content_format = workbook.add_format({
        'text_wrap': True,
        'border': 1,
        'valign': 'top'
    })
    
    # Set column widths
    worksheet.set_column('A:A', 15)  # 카테고리
    worksheet.set_column('B:B', 40)  # 질문
    worksheet.set_column('C:C', 30)  # 답변
    
    # Write user info
    row = 0
    user_info = session.get('user_info', {})
    
    worksheet.merge_range('A1:C1', '기본 정보', header_format)
    row += 1
    
    info_items = [
        ('이름', user_info.get('name', '')),
        ('날짜', user_info.get('date', '')),
        ('나이', user_info.get('age', '')),
        ('성별', '남성' if user_info.get('gender') == 'male' else '여성'),
        ('키', user_info.get('height', '')),
        ('체중', user_info.get('weight', ''))
    ]
    
    for label, value in info_items:
        worksheet.write(row, 0, label, header_format)
        worksheet.merge_range(row, 1, row, 2, value, content_format)
        row += 1
    
    row += 1  # Add empty row
    
    # Write headers for survey responses
    headers = ['카테고리', '질문', '답변']
    for col, header in enumerate(headers):
        worksheet.write(row, col, header, header_format)
    row += 1
    
    # Write survey data
    survey_responses = session['survey_responses']
    for category, responses in survey_responses.items():
        category_title = survey_categories[category]['title']
        
        for response in responses:
            answer = response['answer']
            if isinstance(answer, list):
                answer = ', '.join(answer)
            
            worksheet.write(row, 0, category_title, content_format)
            worksheet.write(row, 1, response['question'], content_format)
            worksheet.write(row, 2, answer, content_format)
            row += 1
    
    workbook.close()
    
    # Prepare the file for download
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

# For Vercel Serverless Function
app = app
