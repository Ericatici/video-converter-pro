#!/usr/bin/env python3
"""
Script para testar notificação de erro enviando um arquivo corrompido
"""
import requests
import sys
from pathlib import Path
import time

AUTH_URL = "http://localhost:8001/auth/login"
UPLOAD_URL = "http://localhost:8002/videos/upload"

def login(username: str, password: str) -> str:
    """Faz login e retorna o token"""
    response = requests.post(AUTH_URL, json={"username": username, "password": password})
    if response.status_code != 200:
        print(f"❌ Erro no login: {response.json()}")
        sys.exit(1)
    token = response.json()["access_token"]
    print(f"✓ Login realizado como: {username}")
    return token

def upload_invalid_file(token: str):
    """Faz upload de um arquivo inválido para gerar erro"""
    
    # Criar arquivo "vídeo" corrompido
    invalid_video = Path("invalid_video.mp4")
    invalid_video.write_text("This is not a valid video file, just text!")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"\n📤 Enviando arquivo corrompido...")
    
    with open(invalid_video, 'rb') as f:
        files = [('files', (invalid_video.name, f, 'video/mp4'))]
        response = requests.post(UPLOAD_URL, headers=headers, files=files)
    
    if response.status_code != 200:
        print(f"❌ Erro no upload: {response.json()}")
        return None
    
    result = response.json()
    print(f"✓ Upload concluído!")
    print(f"  Video ID: {result['videos'][0]['video_id']}")
    print(f"  Status: {result['videos'][0]['status']}\n")
    
    # Limpar arquivo de teste
    invalid_video.unlink()
    
    return result['videos'][0]['video_id']

def check_status(token: str, video_id: int):
    """Verifica o status do vídeo"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"http://localhost:8002/videos/status", headers=headers)
    
    if response.status_code == 200:
        videos = response.json()
        for v in videos:
            if v['id'] == video_id:
                return v['status']
    return None

def main():
    print("🎥 Teste de Notificação de Erro\n")
    
    # Solicita credenciais
    username = input("Usuário: ").strip()
    password = input("Senha: ").strip()
    
    # Login
    token = login(username, password)
    
    # Upload de arquivo corrompido
    video_id = upload_invalid_file(token)
    
    if not video_id:
        print("❌ Falha no upload")
        return
    
    print("⏳ Aguardando processamento (o worker vai tentar processar e gerar erro)...")
    print("   Monitore o webhook_test_server.py em outro terminal para ver a notificação\n")
    
    # Verificar status após alguns segundos
    for i in range(10):
        time.sleep(2)
        status = check_status(token, video_id)
        print(f"   [{i+1}] Status do vídeo {video_id}: {status}")
        
        if status == "error":
            print("\n✅ Erro detectado! A notificação de erro foi enviada ao webhook!")
            print("   Verifique o log do webhook_test_server.py para confirmar a entrega")
            break
        elif status == "completed":
            print("\n⚠️  Arquivo foi processado com sucesso (não foi um erro)")
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelado pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
