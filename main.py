# main.py
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import uvicorn
from datetime import datetime, timedelta
from typing import Optional
from minio import Minio
from minio.error import S3Error
from fastapi import UploadFile, File
import uuid
import os

# برای هش کردن پسورد و JWT
from passlib.context import CryptContext
from jose import JWTError, jwt

import models
from database import SessionLocal, engine
from schemas import PersonCreate, PersonResponse, UserCreate, Token

# ساخت جداول
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MINIO_ENDPOINT = "172.25.229.122:9000"
MINIO_ACCESS_KEY = "QY3AOZRE6M9AIMQLXQEJ"
MINIO_SECRET_KEY = "hEiS8O4hcqCsIbMF8EHXWDgq6SXevejusbyczMeR"
# MINIO_ACCESS_KEY = "admin"
# MINIO_SECRET_KEY = "admin123"
MINIO_BUCKET_NAME = "images"

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False,  # چون http است
)


# --- تنظیمات امنیتی JWT ---
SECRET_KEY = "replace_this_with_a_strong_secret_key"  # حتما در تولید/پروژه واقعی تغییر بده
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1  # یک روز، می‌تونی کم/زیاد کنی

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# dependency دیتابیس
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# کمک‌ها
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# -------------------------------
# اندپوینت: ثبت‌نام کاربر
# -------------------------------
# @app.on_event("startup")
def create_bucket():
    found = minio_client.bucket_exists(MINIO_BUCKET_NAME)
    if not found:
        minio_client.make_bucket(MINIO_BUCKET_NAME)


@app.post("/register", response_model=Token)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    # بررسی وجود username
    existing = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="نام کاربری قبلا استفاده شده است")

    hashed = get_password_hash(user_in.password)
    new_user = models.User(username=user_in.username, hashed_password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": new_user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# -------------------------------
# اندپوینت: لاگین (تبدیل username+password به توکن)
# از OAuth2PasswordRequestForm برای سازگاری با ابزارها استفاده می‌کنیم
# -------------------------------
@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2PasswordRequestForm فیلدها را به صورت form-data ارسال می‌کند: username, password
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user:
        raise HTTPException(status_code=400, detail="نام کاربری یا رمز عبور اشتباه است")

    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="نام کاربری یا رمز عبور اشتباه است")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# -------------------------------
# مثال: اندپوینت که نیازمند توکن است (نحوه استفاده بعدی)
# -------------------------------
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_username(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="معتبر نبودن توکن یا دسترسی ندارید",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username

# نمونه اندپوینت محافظت‌شده — می‌تونی برای گرفتن اطلاعات شخص از national_code از آن استفاده کنی
@app.get("/me")
def read_me(username: str = Depends(get_current_username)):
    return {"username": username}

# -------------------------------
# اندپوینت‌های قبلی (شخص) — بدون تغییر ساختار (اما می‌توانی برای get_person از توکن استفاده کنی)
# -------------------------------
@app.post("/add-person", response_model=PersonResponse)
def add_person(person: PersonCreate, db: Session = Depends(get_db)):
    db_person = db.query(models.Person).filter(models.Person.national_code == person.national_code).first()
    if db_person:
        raise HTTPException(status_code=400, detail="کد ملی قبلا ثبت شده است")

    new_person = models.Person(
        firstname=person.firstname,
        lastname=person.lastname,
        national_code=person.national_code,
        address=person.address,
        phone=person.phone
    )
    db.add(new_person)
    db.commit()
    db.refresh(new_person)
    return new_person

# اگر می‌خواهی get-person را محافظت‌شده کنی، می‌توانی dependency توکن را اضافه کنی.
@app.get("/get-person/{national_code}", response_model=PersonResponse)
def get_person(national_code: str, db: Session = Depends(get_db), username: str = Depends(get_current_username)):
    person = db.query(models.Person).filter(models.Person.national_code == national_code).first()
    if not person:
        raise HTTPException(status_code=404, detail="فردی با این کد ملی یافت نشد")
    return person

@app.post("/upload-image")
def upload_image(file: UploadFile = File(...),):
    create_bucket()
    # 1. بررسی نوع فایل
    if file.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(
            status_code=400,
            detail="فقط فایل تصویری jpg یا png مجاز است"
        )

    # 2. ساخت نام یکتا
    file_ext = os.path.splitext(file.filename)[1]
    # file_ext = 'temp'
    object_name = f"{uuid.uuid4()}{file_ext}"

    try:
        # 3. آپلود در MinIO
        minio_client.put_object(
            bucket_name=MINIO_BUCKET_NAME,
            object_name=object_name,
            data=file.file,
            length=-1,
            part_size=10 * 1024 * 1024,
            content_type=file.content_type
        )

    except S3Error as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "message": "تصویر با موفقیت آپلود شد",
        "object_name": object_name,
        "bucket": MINIO_BUCKET_NAME
    }



if __name__ == "__main__":
    # this is a comment
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
