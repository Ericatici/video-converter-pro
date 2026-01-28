#!/usr/bin/env python3
"""
Script para listar vídeos de um usuário
"""
import requests
import sys
from tabulate import tabulate

AUTH_URL = "http://localhost:8001/auth/login"
STATUS_URL = "http://localhost:8002/videos/status"

def login(username: str, password: str) -> str:
    """Faz login e retorna o token"""
    response = requests.post(AUTH_URL, json={"username": username, "password": password})
    if response.status_code != 200:
        print(f"❌ Erro no login: {response.json()}")
        sys.exit(1)
    token = response.json()["access_token"]
    print(f"✓ Login realizado como: {username}\n")
    return token

def list_videos(token: str) -> list:
    """Lista todos os vídeos do usuário"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(STATUS_URL, headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Erro ao listar vídeos: {response.json()}")
        return []
    
    return response.json()

def main():
    print("🎥 Lista de Vídeos por Usuário\n")
    
    # Solicita credenciais
    username = input("Usuário: ").strip()
    password = input("Senha: ").strip()
    
    # Login
    token = login(username, password)
    
    # Lista vídeos
    videos = list_videos(token)
    
    if not videos:
        print("Nenhum vídeo encontrado.")
        return
    
    # Formata e exibe tabela
    table_data = []
    for v in videos:
        status_emoji = {
            "uploaded": "📤",
            "processing": "⏳",
            "completed": "✅",
            "error": "❌"
        }.get(v["status"], "❓")
        
        table_data.append([
            v["id"],
            v["filename"],
            f"{status_emoji} {v['status']}"
        ])
    
    print(tabulate(
        table_data,
        headers=["ID", "Nome do Arquivo", "Status"],
        tablefmt="grid",
        stralign="left"
    ))
    
    print(f"\n📊 Total: {len(videos)} vídeo(s)")
    
    # Resumo por status
    status_count = {}
    for v in videos:
        status = v["status"]
        status_count[status] = status_count.get(status, 0) + 1
    
    print("\n📈 Resumo:")
    for status, count in sorted(status_count.items()):
        emoji = {
            "uploaded": "📤",
            "processing": "⏳",
            "completed": "✅",
            "error": "❌"
        }.get(status, "❓")
        print(f"   {emoji} {status.capitalize()}: {count}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelado pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
