import requests
from datetime import datetime
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

# Constantes
COLABORADORAS = ["Ana", "Beatriz", "Carla"]
HORARIOS_DISPONIVEIS = ["10:00", "11:00", "14:00", "15:00", "16:00"]
ARQUIVO_AGENDAMENTOS = "agendamentos.txt"
NOME_SALAO = "Bella Beauty Salon"

# Personalidade do Bot
INSTRUCOES_PERSONALIDADE = """
Você é a Bella, a assistente virtual do Bella Beauty Salon, um salão de beleza especializado em cabelos e unhas.
Seu tom deve ser sempre:
- Acolhedor e caloroso, como uma recepcionista experiente de salão
- Profissional mas amigável
- Conhecedor sobre serviços de beleza, cuidados com cabelo e unhas
- Empático com as necessidades das clientes

Ao sugerir serviços ou responder dúvidas:
- Mencione os benefícios dos tratamentos
- Use linguagem que demonstre conhecimento técnico sobre beleza e estética
- Personalize as sugestões conforme as necessidades específicas da cliente
- Sempre que possível, mencione os serviços que o Bella Beauty Salon oferece

Serviços do salão incluem:
- Cortes (modernos, clássicos, repicados)
- Coloração (tintura, mechas, ombré hair, balayage)
- Tratamentos capilares (hidratação, reconstrução, queratinização)
- Penteados (para festas e eventos)
- Manicure e pedicure (simples, decoradas, em gel)
- Tratamentos para unhas (fortalecimento, alongamento)

Você também possui conhecimento especializado em:
- Cuidados diários com diferentes tipos de cabelo
- Tratamentos caseiros para cabelos e unhas
- Identificação de problemas comuns em cabelos e unhas
- Dicas de manutenção entre visitas ao salão
- Produtos recomendados para diferentes necessidades

O salão valoriza atendimento personalizado e resultados que realçam a beleza natural de cada cliente.
Seja sempre prestativa e detalhada ao responder dúvidas sobre cuidados com cabelo e unhas.
"""


def esta_em_horario_comercial():
    """Verifica se o horário atual está dentro do horário comercial (8h-17h)"""
    hora_atual = datetime.now().hour
    return 8 <= hora_atual <= 24


def consultar_gemini(prompt, contexto_conversacional=None):
    """Envia uma consulta para a API do Gemini e retorna a resposta com personalidade"""
    try:
        # Combina a personalidade com o prompt específico
        prompt_completo = f"{INSTRUCOES_PERSONALIDADE}\n\nSolicitação da cliente: {prompt}"
        
        # Adiciona contexto da conversa se fornecido
        if contexto_conversacional:
            prompt_completo += f"\n\nContexto da conversa: {contexto_conversacional}"
        
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [
                {
                    "parts": [{"text": prompt_completo}]
                }
            ]
        }
        
        response = requests.post(URL, headers=headers, json=data, timeout=60)
        
        if response.status_code == 200:
            resposta_json = response.json()
            return resposta_json['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"⚠️ Erro na API (código {response.status_code})"
            
    except requests.exceptions.Timeout:
        return "⚠️ A conexão demorou demais. Tente novamente mais tarde."
    except Exception as e:
        return f"⚠️ Ocorreu um erro: {str(e)}"


def registrar_agendamento(nome, telefone, colaboradora, servico, horario):
    """Salva um novo agendamento no arquivo"""
    with open(ARQUIVO_AGENDAMENTOS, "a", encoding="utf-8") as arquivo:
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
        arquivo.write(f"{timestamp} - Cliente: {nome} - Número: {telefone} - {colaboradora} - {servico} às {horario}\n")


def obter_horarios_ocupados():
    """Carrega os horários já agendados do arquivo"""
    horarios_ocupados = []
    
    if os.path.exists(ARQUIVO_AGENDAMENTOS):
        with open(ARQUIVO_AGENDAMENTOS, "r", encoding="utf-8") as arquivo:
            for linha in arquivo:
                partes = linha.strip().split(" às ")
                if len(partes) > 1:
                    horario = partes[1].strip()
                    horarios_ocupados.append(horario)
                    
    return horarios_ocupados


def exibir_menu():
    """Exibe o menu principal do bot"""
    print(f"\n💬 Olá, eu sou a Bella! ✨ Seja bem-vinda ao {NOME_SALAO}!")
    print("Como posso ajudar você hoje?")
    print("1️⃣ Agendar horário")
    print("2️⃣ Sugestões e dúvidas sobre serviços")
    print("3️⃣ Falar com uma atendente")
    print("0️⃣ Sair")


def exibir_horarios_disponiveis(horarios_livres):
    """Exibe os horários disponíveis numerados para seleção"""
    print("\n🕒 Horários disponíveis:")
    for i, horario in enumerate(horarios_livres, 1):
        print(f"{i}. {horario}")


def selecionar_horario(horarios_livres):
    """Permite ao usuário selecionar um horário da lista numerada"""
    exibir_horarios_disponiveis(horarios_livres)
    
    while True:
        try:
            escolha = input("\nDigite o número do horário desejado: ").strip()
            indice = int(escolha) - 1
            
            if 0 <= indice < len(horarios_livres):
                return horarios_livres[indice]
            else:
                print(f"⚠️ Por favor, digite um número entre 1 e {len(horarios_livres)}.")
        except ValueError:
            print("⚠️ Por favor, digite apenas o número correspondente ao horário.")


def processar_agendamento():
    """Processa o fluxo de agendamento"""
    if not esta_em_horario_comercial():
        print("⏰ Nosso atendimento é das 8h às 17h. Por favor, envie mensagem nesse horário.")
        return
        
    resposta = input("Gostaria de agendar um horário? (Sim/Não): ").strip().lower()
    if resposta != "sim":
        print("😊 Tudo bem! Quando quiser agendar, estou aqui para ajudar!")
        return
        
    # Coleta informações do cliente
    nome_cliente = input("Qual é o seu nome? ").strip()
    numero_cliente = input("Qual é o seu número de telefone? ").strip()
    
    # Seleciona colaboradora
    colaboradora = input(f"Com qual profissional deseja agendar? Temos: {', '.join(COLABORADORAS)}: ").strip().title()
    if colaboradora not in COLABORADORAS:
        print("⚠️ Não encontramos essa profissional em nossa equipe.")
        return
        
    # Seleciona serviço
    servico = input("Qual serviço você deseja? (ex: corte, coloração, manicure): ").strip()
    if "não sei" in servico.lower() or "indecisa" in servico.lower():
        dica = consultar_gemini(
            "Uma cliente está indecisa sobre qual serviço escolher. Sugira 3 opções populares de serviços, explicando brevemente os benefícios de cada um.",
            f"Cliente: {nome_cliente}"
        )
        print("\n💡 Sugestões para você:\n", dica)
        servico = input("\nQual serviço você gostaria de agendar? ").strip()
    
    # Verifica horários disponíveis
    horarios_ocupados = obter_horarios_ocupados()
    horarios_livres = [h for h in HORARIOS_DISPONIVEIS if h not in horarios_ocupados]
    
    if not horarios_livres:
        print("⚠️ Todos os horários de hoje estão ocupados. Podemos verificar disponibilidade para amanhã!")
        return
    
    # Seleciona horário usando a nova interface numerada
    horario = selecionar_horario(horarios_livres)
        
    # Confirma agendamento
    registrar_agendamento(nome_cliente, numero_cliente, colaboradora, servico, horario)
    
    # Mensagem personalizada de confirmação via Gemini
    confirmacao = consultar_gemini(
        f"Crie uma mensagem de confirmação de agendamento entusiasmada e personalizada para uma cliente chamada {nome_cliente} que agendou {servico} com {colaboradora} às {horario}. Mantenha a mensagem curta e amigável.",
        f"Cliente: {nome_cliente}, Serviço: {servico}"
    )
    
    print(f"\n✅ {confirmacao}")


def sugestoes_e_duvidas():
    """Função unificada para lidar com sugestões e dúvidas"""
    print("\n🌟 Como posso ajudar você hoje?")
    print("1. Sugestões de serviços para você")
    print("2. Tirar dúvidas sobre serviços e cuidados")
    print("0. Voltar ao menu principal")
    
    escolha = input("\nDigite o número da opção desejada: ").strip()
    
    if escolha == "1":
        obter_sugestoes()
    elif escolha == "2":
        responder_duvidas()
    elif escolha == "0":
        return
    else:
        print("❌ Opção inválida. Por favor, escolha uma das opções disponíveis.")


def obter_sugestoes():
    """Solicita sugestões de serviços com base nas preferências do cliente"""
    print("🔎 Vamos encontrar o serviço perfeito para você...")
    
    gosto = input("Por favor, conte-me um pouco sobre o que você está procurando ou sua situação atual "
                 "(ex: 'meu cabelo está danificado', 'quero algo para uma festa', 'minhas unhas quebram facilmente'): ").strip()
    
    if not gosto:
        print("⚠️ Para que eu possa sugerir o melhor serviço, preciso saber um pouco mais sobre o que você procura.")
        return
        
    prompt = f"Uma cliente do salão de beleza compartilhou a seguinte necessidade/situação: '{gosto}'. " \
             f"Sugira 2-3 serviços específicos do nosso salão que seriam ideais para ela, explicando brevemente por que cada um " \
             f"seria benéfico no caso dela. Seja específica, acolhedora e demonstre conhecimento técnico de beleza."
    
    sugestao = consultar_gemini(prompt)
    print("\n✨ Recomendações personalizadas para você:\n", sugestao)


def responder_duvidas():
    """Responde às dúvidas da cliente sobre os serviços e cuidados com cabelo/unhas"""
    print("❓ Em que posso ajudar? Sou especialista em cuidados com cabelo e unhas!")
    
    duvida = input("Qual é a sua dúvida? Pode perguntar sobre nossos serviços, cuidados com cabelo, cuidados com unhas, ou qualquer outra questão relacionada à beleza: ").strip()
    
    if not duvida:
        print("⚠️ Por favor, faça sua pergunta para que eu possa ajudar.")
        return
    
    prompt = f"Uma cliente do salão de beleza tem a seguinte dúvida: '{duvida}'. " \
             f"Responda de forma completa, educada e informativa, demonstrando conhecimento técnico sobre tratamentos " \
             f"de beleza e cuidados com cabelo e unhas. Use linguagem acessível, mas técnica quando necessário. " \
             f"Forneça informações práticas e úteis. Se apropriado, sugira serviços do nosso salão que possam " \
             f"ajudar com a questão dela ou produtos para uso em casa."
    
    resposta = consultar_gemini(prompt)
    print("\n📝 Resposta:", resposta)
    
    # Pergunta se a resposta foi útil
    util = input("\nEssa resposta foi útil para você? (Sim/Não): ").strip().lower()
    if util != "sim":
        mais_info = input("Por favor, me conte mais detalhes para que eu possa ajudar melhor: ").strip()
        if mais_info:
            contexto = f"A cliente não ficou satisfeita com a resposta anterior sobre: '{duvida}'. " \
                      f"Ela adicionou as seguintes informações: '{mais_info}'. " \
                      f"Por favor, forneça uma resposta mais direcionada e específica, usando seu conhecimento especializado em cuidados com cabelo e unhas."
            
            nova_resposta = consultar_gemini(contexto)
            print("\n📝 Resposta atualizada:", nova_resposta)


def main():
    """Função principal do programa"""
    while True:
        exibir_menu()
        escolha = input("\nDigite o número da opção desejada: ").strip()
        
        if escolha == "1":
            processar_agendamento()
        elif escolha == "2":
            sugestoes_e_duvidas()
        elif escolha == "3":
            print("📞 Você será redirecionada para uma atendente humana. Por favor, aguarde um momento...")
        elif escolha == "0":
            mensagem_despedida = consultar_gemini("Crie uma mensagem de despedida calorosa e breve para uma cliente do salão de beleza que está encerrando a conversa.")
            print(f"\n👋 {mensagem_despedida}")
            break
        else:
            print("❌ Opção inválida. Por favor, escolha uma das opções disponíveis.")


if __name__ == "__main__":
    main()