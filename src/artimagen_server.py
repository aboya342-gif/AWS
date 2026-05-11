import cv2
import numpy as np
from fastapi import FastAPI, Form
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

# HTML 뷰어(프론트엔드)에서 접근할 수 있도록 CORS 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 스크립트 파일 위치를 기준으로 절대 경로 계산
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_PATH = os.path.join(BASE_DIR, "../images/sem_line_width_1778403346454.png")

@app.post("/process_image")
async def process_image(
    vacc: float = Form(...),
    iprobe: float = Form(...),
    drift: float = Form(...)
):
    """
    ARTIMAGEN 이론을 바탕으로 파이썬(OpenCV/NumPy)을 사용하여 
    물리적 영상 왜곡, 노이즈, 차징 현상을 픽셀 단위로 시뮬레이션합니다.
    """
    # 1. 이미지 로드 (그레이스케일)
    if not os.path.exists(IMAGE_PATH):
        return Response(content="Image not found", status_code=404)
        
    img = cv2.imread(IMAGE_PATH, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return Response(content="Failed to load image", status_code=500)

    img_float = img.astype(np.float32)
    h, w = img_float.shape

    # 2. 상호작용 부피 확산 (Interaction Volume Blur)
    # 가속 전압이 높을수록 전자가 깊게 침투하여 표면 해상도가 흐려짐
    blur_level = 0
    if vacc > 5.0:
        blur_level = int((vacc - 5.0) * 0.5)
        # 커널 사이즈는 홀수여야 함
        if blur_level % 2 == 0:
            blur_level += 1
        if blur_level >= 3:
            img_float = cv2.GaussianBlur(img_float, (blur_level, blur_level), 0)

    # 3. 빔 드리프트 (Geometric Skew Distortion)
    # 빔이 스캔하는 동안 스테이지나 빔이 밀려서 이미지가 사선으로 찌그러지는 현상
    if drift > 0:
        skew_angle = drift * 0.05
        # 변환 행렬 [1, tan(angle), 0; 0, 1, 0]
        pts1 = np.float32([[0, 0], [w, 0], [0, h]])
        # y축에 따라 x축으로 밀리도록(skew) 좌표 계산
        pts2 = np.float32([
            [0, 0], 
            [w, 0], 
            [-h * np.tan(skew_angle), h]
        ])
        matrix = cv2.getAffineTransform(pts1, pts2)
        # 테두리 바깥은 검정(0)으로 채움
        img_float = cv2.warpAffine(img_float, matrix, (w, h), borderValue=0)

    # 4. 차징(Charging) 및 포화(Saturation)
    # 빔 에너지가 높고 밝은 부분(돌출부)일수록 2차 전자가 과다 방출되어 픽셀이 하얗게 타버림
    charging = 0
    if vacc > 3.0:
        charging = ((vacc - 3.0) / 12.0) * (iprobe / 100.0)
    
    if charging > 0:
        # 밝기(Signal)가 높은 부분에만 지수적으로 밝기 증가
        mask = img_float > 100
        boost = (img_float[mask] - 100) * charging * 2.5
        img_float[mask] += boost

    # 5. 샷 노이즈 (Shot Noise - 포아송/가우시안 근사)
    # 전류(iprobe)가 낮을수록 SNR이 급격히 나빠져 지글거리는 노이즈 발생
    noise_std = 100.0 / iprobe
    noise = np.random.normal(0, noise_std, img_float.shape)
    img_float = img_float + noise

    # 6. 최종 픽셀 값 클리핑 (0~255) 및 반환
    img_final = np.clip(img_float, 0, 255).astype(np.uint8)
    
    # JPG/PNG 바이트로 인코딩하여 반환
    _, encoded_img = cv2.imencode('.png', img_final)
    return Response(content=encoded_img.tobytes(), media_type="image/png")

if __name__ == "__main__":
    import uvicorn
    # 서버 실행: python src/artimagen_server.py
    print("ARTIMAGEN 파이썬 백엔드 서버가 시작됩니다...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
