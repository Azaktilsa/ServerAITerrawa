# app/routes.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import base64
import smtplib
import os
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
import re

# Cargar .env si aún no lo ha hecho main.py (opcional si ya cargaste antes)
load_dotenv()

router = APIRouter()


class InvoiceRequest(BaseModel):
    recipient: str
    pdf_base64: str
    subject: str
    html_body: str


def is_valid_email(email: str) -> bool:
    """Validación manual más flexible que EmailStr"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


@router.post("/send-invoice")
async def send_invoice(request: InvoiceRequest):
    try:
        # 1. Validar el correo manualmente
        if not is_valid_email(request.recipient):
            raise HTTPException(
                status_code=400,
                detail=f"Formato de correo no válido: {request.recipient}"
            )

        # 2. Configuración SMTP desde variables de entorno
        email_user = os.getenv("EMAIL_USER")
        email_pass = os.getenv("EMAIL_PASS")

        if not email_user or not email_pass:
            raise HTTPException(
                status_code=500,
                detail="Variables de entorno EMAIL_USER o EMAIL_PASS no están "
                       "definidas. Asegúrate de configurarlas correctamente."
            )

        # 3. Decodificar el PDF base64
        try:
            pdf_bytes = base64.b64decode(request.pdf_base64)
        except Exception as decode_error:
            raise HTTPException(
                status_code=400,
                detail=f"Error al decodificar el PDF base64: {decode_error}"
            )

        # 4. Preparar mensaje de correo
        msg = MIMEMultipart()
        msg["From"] = email_user
        msg["To"] = request.recipient
        msg["Subject"] = request.subject

        msg.attach(MIMEText(request.html_body, "html"))

        # 5. Adjuntar PDF
        part = MIMEApplication(pdf_bytes, Name="guia.pdf")
        part["Content-Disposition"] = 'attachment; filename="guia.pdf"'
        msg.attach(part)

        # 6. Enviar correo
        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(email_user, email_pass)
                server.sendmail(email_user, request.recipient, msg.as_string())
            return {"message": "Correo enviado con éxito"}
        except smtplib.SMTPRecipientsRefused:
            raise HTTPException(
                status_code=400,
                detail=f"El servidor rechazó el correo: {request.recipient}"
            )
        except smtplib.SMTPAuthenticationError:
            raise HTTPException(
                status_code=500,
                detail="Error de autenticación SMTP. "
                "Verifica las credenciales."
            )
        except Exception as smtp_error:
            raise HTTPException(
                status_code=500,
                detail=f"Error al enviar correo: {str(smtp_error)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado: {str(e)}"
        )
