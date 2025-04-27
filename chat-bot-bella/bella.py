import requests
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

colaboradoras = ["Ana", "Beatriz", "Carla"]
horarios_disponiveis = ["10:00", "11:00", "14:00", "16:00"]

def horario_comercial():
    agora = datetime.now()
    hora = agora.hour
    return 8 <= hora <= 17

def perguntar_gemini(texto_usuario):
    try:
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [
                {
                    "parts": [{"text": texto_usuario}]
                }
            ]
        }
        response = requests.post(URL, headers=headers, json=data, timeout=60) 
        if response.status_code == 200:
            resposta_json = response.json()
            return resposta_json['candidates'][0]['content']['parts'][0]['text']
        else:
            return "⚠️ Não foi possível obter uma resposta agora."
    except requests.exceptions.Timeout:
        return "⚠️ A conexão demorou demais. Tente novamente mais tarde."
    except Exception as e:
        return f"⚠️ Ocorreu um erro: {e}"

def salvar_agendamento(nome_cliente, numero_cliente, colaboradora, servico, horario):
    with open("agendamentos.txt", "a", encoding="utf-8") as arquivo:
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        arquivo.write(f"{agora} - Cliente: {nome_cliente} - Número: {numero_cliente} - {colaboradora} - {servico} às {horario}\n")

def carregar_agendamentos():
    horarios_ocupados = []
    if os.path.exists("agendamentos.txt"):
        with open("agendamentos.txt", "r", encoding="utf-8") as arquivo:
            for linha in arquivo:
                partes = linha.strip().split(" às ")
                if len(partes) > 1:
                    horario = partes[1]
                    horarios_ocupados.append(horario)
    return horarios_ocupados

def menu_bella_bot():
    print("\n💬 Olá, eu sou a Bella Bot! ✨ Seja bem-vinda ao nosso salão!")
    print("O que você deseja fazer hoje?")
    print("1️⃣ Agendar horário")
    print("2️⃣ Ver sugestões de serviços")
    print("3️⃣ Falar com uma atendente")
    print("0️⃣ Sair")

while True:
    menu_bella_bot()
    escolha = input("\nDigite o número da opção desejada: ").strip()

    if escolha == "1":
        if horario_comercial():
            resposta = input("Gostaria de agendar um horário? (Sim/Não): ").strip().lower()
            if resposta == "sim":
                nome_cliente = input("Qual é o seu nome? ").strip()
                numero_cliente = input("Qual é o seu número de telefone? ").strip()

                colaboradora = input(f"Com qual colaboradora deseja agendar? Temos: {', '.join(colaboradoras)}: ").strip().title()

                if colaboradora in colaboradoras:
                    servico = input("Qual serviço você deseja? (ex: cabelo, unha, maquiagem): ").strip()

                    if "não sei" in servico.lower() or "indecisa" in servico.lower():
                        dica = perguntar_gemini("Sugira serviços de salão de beleza para uma cliente indecisa.")
                        print("💡 Sugestão para você:", dica)

                    horarios_ocupados = carregar_agendamentos()
                    horarios_livres = [h for h in horarios_disponiveis if h not in horarios_ocupados]

                    if horarios_livres:
                        horario = input(f"Escolha um horário disponível: {', '.join(horarios_livres)}: ").strip()

                        if horario in horarios_livres:
                            print(f"✅ Agendamento confirmado com {colaboradora} para {servico} às {horario}. Obrigada, {nome_cliente}! 💖")
                            salvar_agendamento(nome_cliente, numero_cliente, colaboradora, servico, horario)
                        else:
                            print("⚠️ Desculpe, esse horário não está disponível.")
                    else:
                        print("⚠️ Todos os horários de hoje estão ocupados. Tente novamente amanhã!")
                else:
                    print("⚠️ Não encontramos essa colaboradora.")
            else:
                print("😊 Tudo bem! Quando quiser agendar, estou aqui!")
        else:
            print("⏰ Nosso atendimento é das 8h às 17h. Por favor, envie mensagem nesse horário.")

    elif escolha == "2":
        print("🔎 Buscando sugestões especiais para você...")

        gosto = input("Por favor, compartilhe seu gosto ou preferência para que eu possa sugerir um serviço. (ex: 'meu cabelo está danificado', 'quero algo relaxante', 'quero algo rápido', etc.): ").strip()

        if gosto:
            sugestao_com_base_no_gosto = perguntar_gemini(f"Com base na preferência da cliente: {gosto}, quais serviços de salão você sugere?")
            print("✨ Sugestões:", sugestao_com_base_no_gosto)
        else:
            print("⚠️ Por favor, forneça um gosto ou preferência para receber sugestões.")

    elif escolha == "3":
        print("📞 Você será redirecionada para uma atendente. Por favor, aguarde...")

    elif escolha == "0":
        print("👋 Obrigada por usar a Bella Bot! Até a próxima!")
        break

    else:
        print("❌ Opção inválida. Tente novamente.")
