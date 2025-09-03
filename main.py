from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import tempfile
import shutil
import os
import uuid
from nodes.level_measurement import level_measurement
from nodes.text_to_speech import text_to_speech
from nodes.generate_plan import generate_plan, generate_speech_therapy_plan

app = FastAPI()

PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "public")
os.makedirs(PUBLIC_DIR, exist_ok=True)
app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")

@app.get("/health")
def health():
    return {"status": "API is running"}

@app.post("/level_measurement")
def level_measurement_endpoint(
    audio_file: UploadFile = File(...),
    reference_text: str = Form(...),
    language: str = Form("en-US")
):
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmp_audio_path = os.path.join(tmpdirname, audio_file.filename)
        with open(tmp_audio_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        result = level_measurement(tmp_audio_path, reference_text, language)
    return JSONResponse(content=result)

@app.post("/text_to_speach")
def text_to_speach_endpoint(
    request: Request,
    text: str = Form(...),
    voice_name: str = Form(...),
):
    result = text_to_speech(text=text, voice_name=voice_name, output_dir=PUBLIC_DIR)
    if result.get("success") and result.get("filename"):
        filename = result["filename"]
        try:
            download_url = str(request.url_for("public", path=filename))
        except Exception:
            download_url = f"/public/{filename}"
        return JSONResponse(content={
            "success": True,
            "message": result.get("message", "Speech synthesized successfully."),
            "filename": filename,
            "download_url": download_url,
        })
    return JSONResponse(content=result, status_code=500)

@app.post("/generate_speech_plan")
def generate_speech_plan_endpoint(
    child_age: int = Form(..., description="Child's age (2-8 years)"),
    delay_level: str = Form(..., description="Speech delay level: slight delay, medium delay, or severe delay"),
    language: str = Form(default="English", description="Primary language"),
    daily_time_minutes: int = Form(default=15, description="Available practice time per day in minutes"),
    plan_duration_weeks: int = Form(default=4, description="Plan duration in weeks (1-12)"),
    words_child_can_speak: str = Form(default="", description="Words the child can already speak (comma-separated, e.g., 'mama,dada,ball')"),
    additional_info: str = Form(default="", description="Additional information about the child")
):
    """Generate a structured speech therapy plan for children with speech delays.
    
    This endpoint creates a detailed week-by-week plan with daily word lists and activities.
    """
    
    if child_age < 2 or child_age > 8:
        return JSONResponse(
            status_code=400, 
            content={"success": False, "message": "Child age must be between 2 and 8 years"}
        )
    
    if delay_level.lower() not in ["slight delay", "medium delay", "severe delay"]:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Delay level must be 'slight delay', 'medium delay', or 'severe delay'"}
        )
    
    if plan_duration_weeks < 1 or plan_duration_weeks > 12:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Plan duration must be between 1 and 12 weeks"}
        )

    result = generate_speech_therapy_plan(
        child_age=child_age,
        delay_level=delay_level.lower(),
        language=language,
        daily_time_minutes=daily_time_minutes,
        plan_duration_weeks=plan_duration_weeks,
        words_child_can_speak=words_child_can_speak,
        additional_info=additional_info
    )
    
    status = 200 if result.get("success") else 500
    return JSONResponse(status_code=status, content=result)

@app.post("/generate_plan")
def generate_plan_endpoint(
    system_prompt: str = Form(...),
    context: str = Form(...),
    objective: str = Form(...),
    constraints: str | None = Form(None),
    steps_hint: int | None = Form(None),
):
    """Generate a structured plan using form fields like other endpoints.

    Form fields:
    - system_prompt: Optional instructions for the agent
    - context: Required long text with details to ground the plan
    - objective: Optional objective string
    - constraints: Optional string; can be JSON list, newline- or comma-separated
    - steps_hint: Optional integer suggesting approximate number of steps
    """

    constraints_list = None
    if constraints:
        parts = [s.strip() for s in constraints.split(",") if s.strip()]
        constraints_list = parts if parts else None

    result = generate_plan(
        system_prompt=system_prompt,
        context=context,
        objective=objective,
        constraints=constraints_list,
        steps_hint=steps_hint,
    )
    
    status = 200 if result.get("success") else 500
    
    return JSONResponse(status_code=status, content=result)

def main():
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
