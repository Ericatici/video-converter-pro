#!/usr/bin/env python3
"""
Script para testar upload múltiplo de vídeos
"""
import requests
import sys
from pathlib import Path

AUTH_URL = "http://localhost:8001/auth/login"
UPLOAD_URL = "http://localhost:8002/videos/upload"

def login(username: str, password: str) -> str:
    """Faz login e retorna o token"""
    response = requests.post(AUTH_URL, json={"username": username, "password": password})
    if response.status_code != 200:
        print(f"❌ Erro no login: {response.json()}")
        sys.exit(1)
    token = response.json()["access_token"]
    print(f"✓ Login realizado com sucesso")
    return token

def upload_multiple_videos(token: str, video_paths: list) -> dict:
    """Faz upload de múltiplos vídeos"""
    files = []
    for path in video_paths:
        if not Path(path).exists():
            print(f"⚠️  Arquivo não encontrado: {path}")
            continue
        files.append(('files', (Path(path).name, open(path, 'rb'), 'video/mp4')))
    
    if not files:
        print("❌ Nenhum arquivo válido para upload")
        return None
    
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"\n📤 Enviando {len(files)} arquivo(s)...")
    response = requests.post(UPLOAD_URL, headers=headers, files=files)
    
    # Fecha os arquivos
    for _, (_, file_obj, _) in files:
        file_obj.close()
    
    if response.status_code != 200:
        print(f"❌ Erro no upload: {response.json()}")
        return None
    
    return response.json()

def main():
    print("🎥 Teste de Upload Múltiplo de Vídeos\n")
    
    # Solicita credenciais
    username = input("Usuário: ").strip()
    password = input("Senha: ").strip()
    
    # Login
    token = login(username, password)
    
    # Solicita caminhos dos vídeos
    print("\nDigite os caminhos dos vídeos (um por linha, linha vazia para finalizar):")
    print("(Você pode arrastar os arquivos para o terminal ou colar o caminho)\n")
    video_paths = []
    while True:
        path = input(f"Vídeo {len(video_paths) + 1}: ").strip()
        if not path:
            break
        # Remove aspas do início e fim (se existirem)
        path = path.strip('"').strip("'")
        
        # Verifica se o arquivo existe
        if Path(path).exists():
            video_paths.append(path)
            print(f"   ✓ Arquivo válido: {Path(path).name}")
        else:
            print(f"   ⚠️  Arquivo não encontrado, tente novamente")
            continue
    
    if not video_paths:
        print("❌ Nenhum vídeo informado")
        return
    
    # Upload
    result = upload_multiple_videos(token, video_paths)
    
    if result:
        print(f"\n✅ Upload concluído com sucesso!")
        print(f"   Total enviado: {result['uploaded']} vídeo(s)\n")
        for video in result['videos']:
            print(f"   • {video['filename']}")
            print(f"     ID: {video['video_id']}")
            print(f"     Status: {video['status']}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelado pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
