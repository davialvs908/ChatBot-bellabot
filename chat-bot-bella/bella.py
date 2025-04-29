import requests
from datetime import datetime
import os
from dotenv import load_dotenv
import time
import random

# Carrega variáveis de ambiente
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

# Constantes
COLABORADORAS = ["Ana", "Beatriz", "Carla"]
HORARIOS_DISPONIVEIS = ["10:00", "11:00", "14:00", "15:00", "16:00"]
ARQUIVO_AGENDAMENTOS = "agendamentos.txt"
NOME_SALAO = "Bella Beauty Salon"

# Personalidade do Bot com restrições explícitas
INSTRUCOES_PERSONALIDADE = """
Você é a Bella, a assistente virtual do Bella Beauty Salon, um salão de beleza especializado APENAS em cabelos e unhas.
Seu tom deve ser sempre:
- Acolhedor e caloroso, como uma recepcionista experiente de salão
- Profissional mas amigável
- Conhecedor sobre serviços de beleza, cuidados com cabelo e unhas
- Empático com as necessidades das clientes

RESTRIÇÕES RÍGIDAS:
- Você DEVE responder APENAS assuntos diretamente relacionados a cabelos e unhas
- Você DEVE recusar qualquer pergunta fora do contexto de salão de beleza
- Você DEVE recusar perguntas sobre maquiagem, estética corporal, ou outros serviços não oferecidos
- Você DEVE recusar perguntas inapropriadas, ofensivas, ou de baixo escalão
- Você NUNCA deve dar conselhos médicos, apenas sugestões estéticas
- Você NUNCA deve responder perguntas sobre política, religião, notícias ou temas controversos
- Você NUNCA deve fornecer dados falsos para agradar ao cliente

Quando receber uma pergunta fora do escopo, responda educadamente:
"Desculpe, como assistente especializada do Bella Beauty Salon, posso ajudar apenas com assuntos relacionados a cabelos e unhas. Posso responder sobre nossos serviços de cabelo e manicure/pedicure. Em que posso ajudá-la com esses serviços?"

Serviços do salão LIMITADOS a:
- Cortes (modernos, clássicos, repicados)
- Coloração (tintura, mechas, ombré hair, balayage)
- Tratamentos capilares (hidratação, reconstrução, queratinização)
- Penteados (para festas e eventos)
- Manicure e pedicure (simples, decoradas, em gel)
- Tratamentos para unhas (fortalecimento, alongamento)

Você também possui conhecimento especializado APENAS em:
- Cuidados diários com diferentes tipos de cabelo
- Tratamentos caseiros para cabelos e unhas
- Identificação de problemas comuns em cabelos e unhas
- Dicas de manutenção entre visitas ao salão
- Produtos recomendados para diferentes necessidades de cabelo e unhas

O salão valoriza atendimento personalizado e resultados que realçam a beleza natural de cada cliente.
Seja sempre prestativa e detalhada ao responder dúvidas sobre cuidados com cabelo e unhas.
"""

# Respostas pré-definidas para uso quando a API falhar
RESPOSTAS_FALLBACK = [
    "Compreendi sua solicitação sobre cabelos e unhas. Nossa equipe especializada está pronta para atendê-la com os melhores serviços. Gostaria de agendar um horário para uma avaliação personalizada?",
    "Obrigada por sua pergunta sobre nossos serviços. O Bella Beauty Salon oferece tratamentos exclusivos para cabelos e unhas. Podemos sugerir opções que se adequem perfeitamente às suas necessidades.",
    "Entendi sua necessidade! Nossos profissionais são especializados em transformar cabelos e unhas. Que tal agendar uma consulta para discutirmos as melhores opções para você?",
    "Agradeço seu interesse em nossos serviços. Temos diversas opções de tratamentos para cabelos e unhas que podem resolver essa questão. Gostaria de conhecer mais detalhes?",
    "Sua satisfação é nossa prioridade! Para responder de forma personalizada sobre esse assunto de cabelos e unhas, recomendo que converse diretamente com uma de nossas especialistas."
]


def esta_em_horario_comercial():
    """Verifica se o horário atual está dentro do horário comercial (8h-17h)"""
    hora_atual = datetime.now().hour
    return 8 <= hora_atual <= 24


def verificar_topico_permitido(texto):
    """Verifica se o assunto está dentro do escopo permitido (cabelos e unhas)"""
    # Lista de palavras-chave relacionadas aos serviços permitidos
    palavras_cabelo = ['cabelo', 'corte', 'tintura', 'coloração', 'mechas', 'penteado', 'alisamento',
                      'hidratação', 'reconstrução', 'queratina', 'shampoo', 'condicionador', 'tratamento',
                      'raiz', 'ponta', 'fio', 'volume', 'brilho', 'caspa', 'couro cabeludo', 'secador', 
                      'chapinha', 'babyliss', 'cachos', 'lisos', 'ondulados', 'crespos', 'loiro', 
                      'morena', 'ruiva', 'grisalho', 'tinta', 'descoloração', 'escova', 'permanente']
                      
    palavras_unhas = ['unha', 'manicure', 'pedicure', 'esmalte', 'cutícula', 'gel', 'alongamento', 
                      'fibra', 'acrílica', 'nail art', 'francesinha', 'decoração', 'base', 'top coat', 
                      'acetona', 'lixa', 'alicate', 'fortalecedor', 'quebradiças', 'formato', 'curvatura']
                      
    palavras_salao = ['agendar', 'marcar', 'horário', 'serviço', 'atendimento', 'profissional', 'salão', 
                      'estilista', 'cabeleireiro', 'preço', 'valor', 'duração', 'produto', 'promoção',
                      'desconto', 'bela', 'bella']
    
    # Combina todas as palavras-chave
    todas_permitidas = palavras_cabelo + palavras_unhas + palavras_salao
    
    # Verifica se pelo menos uma palavra-chave está presente no texto
    texto = texto.lower()
    for palavra in todas_permitidas:
        if palavra.lower() in texto:
            return True
            
    # Se nenhuma palavra-chave for encontrada, o assunto está fora do escopo
    return False


def consultar_gemini(prompt, contexto_conversacional=None, verificar_escopo=True, max_tentativas=3):
    """Envia uma consulta para a API do Gemini e retorna a resposta com personalidade"""
    # Verifica se o prompt está dentro do escopo, se necessário
    if verificar_escopo and not verificar_topico_permitido(prompt):
        return ("Desculpe, como assistente especializada do Bella Beauty Salon, posso ajudar apenas com "
               "assuntos relacionados a cabelos e unhas. Posso responder sobre nossos serviços "
               "de cabelo e manicure/pedicure. Em que posso ajudá-la com esses serviços?")
    
    # Combina a personalidade com o prompt específico
    prompt_completo = f"{INSTRUCOES_PERSONALIDADE}\n\nSolicitação da cliente: {prompt}"
    
    # Adiciona contexto da conversa se fornecido
    if contexto_conversacional:
        prompt_completo += f"\n\nContexto da conversa: {contexto_conversacional}"
    
    for tentativa in range(max_tentativas):
        try:
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
            elif response.status_code == 503:
                # Serviço indisponível, aguardar e tentar novamente
                wait_time = (2 ** tentativa) + random.uniform(0, 1)  # Backoff exponencial com jitter
                print(f"⚠️ Serviço temporariamente indisponível. Tentando novamente em {wait_time:.2f} segundos...")
                time.sleep(wait_time)
                continue
            else:
                # Se chegou aqui em última tentativa, retornar resposta de fallback
                if tentativa == max_tentativas - 1:
                    return random.choice(RESPOSTAS_FALLBACK)
                # Senão, aguardar e tentar novamente
                wait_time = (2 ** tentativa) + random.uniform(0, 1)
                print(f"⚠️ Erro na API (código {response.status_code}). Tentando novamente em {wait_time:.2f} segundos...")
                time.sleep(wait_time)
                    
        except requests.exceptions.Timeout:
            # Em caso de timeout, pode tentar novamente ou retornar fallback
            if tentativa == max_tentativas - 1:
                return random.choice(RESPOSTAS_FALLBACK)
            # Aguardar um pouco mais na próxima tentativa
            wait_time = (2 ** tentativa) + random.uniform(0, 1)
            print(f"⚠️ Tempo esgotado. Tentando novamente em {wait_time:.2f} segundos...")
            time.sleep(wait_time)
        except Exception as e:
            # Para outros erros, tentar algumas vezes e depois usar fallback
            if tentativa == max_tentativas - 1:
                return random.choice(RESPOSTAS_FALLBACK)
            wait_time = (2 ** tentativa) + random.uniform(0, 1)
            print(f"⚠️ Erro: {str(e)}. Tentando novamente em {wait_time:.2f} segundos...")
            time.sleep(wait_time)

    # Se todas as tentativas falharem, usar resposta de fallback
    return random.choice(RESPOSTAS_FALLBACK)


def criar_arquivo_agendamentos_se_nao_existir():
    """Cria o arquivo de agendamentos se não existir"""
    if not os.path.exists(ARQUIVO_AGENDAMENTOS):
        with open(ARQUIVO_AGENDAMENTOS, "w", encoding="utf-8") as arquivo:
            arquivo.write("# Registro de Agendamentos do Bella Beauty Salon\n")
            arquivo.write("# Formato: Data/Hora - Cliente - Número - Profissional - Serviço às Horário\n\n")


def registrar_agendamento(nome, telefone, colaboradora, servico, horario):
    """Salva um novo agendamento no arquivo"""
    criar_arquivo_agendamentos_se_nao_existir()
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
    print("Especializada em serviços de cabelo e unhas.")
    print("Como posso ajudar você hoje?")
    print("1️⃣ Agendar horário")
    print("2️⃣ Sugestões e dúvidas sobre cabelos e unhas")
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
    print(f"Profissionais disponíveis: {', '.join(COLABORADORAS)}")
    while True:
        colaboradora = input("Com qual profissional deseja agendar? ").strip().title()
        if colaboradora in COLABORADORAS:
            break
        print("⚠️ Não encontramos essa profissional em nossa equipe. Por favor, escolha entre as disponíveis.")
        
    # Seleciona serviço com verificação de escopo
    while True:
        servico = input("Qual serviço você deseja? (Somente serviços de cabelo ou unhas): ").strip()
        
        # Verifica se o serviço está no escopo permitido
        if not verificar_topico_permitido(servico):
            print("⚠️ Desculpe, nosso salão oferece apenas serviços de cabelo e unhas.")
            continue
            
        if "não sei" in servico.lower() or "indecisa" in servico.lower():
            try:
                dica = consultar_gemini(
                    "Uma cliente está indecisa sobre qual serviço escolher entre cabelo e unhas. Sugira 3 opções populares de serviços, explicando brevemente os benefícios de cada um.",
                    f"Cliente: {nome_cliente}",
                    verificar_escopo=False
                )
                print("\n💡 Sugestões para você:\n", dica)
            except Exception:
                print("\n💡 Sugestões populares para você:")
                print("1. Hidratação profunda - Restaura a saúde dos fios danificados")
                print("2. Manicure em gel - Unhas fortes e duradouras por semanas")
                print("3. Corte repicado - Dá movimento e volume aos cabelos")
                
            servico = input("\nQual serviço você gostaria de agendar? ").strip()
            
            # Verifica novamente se o serviço escolhido está no escopo
            if not verificar_topico_permitido(servico):
                print("⚠️ Desculpe, nosso salão oferece apenas serviços de cabelo e unhas.")
                continue
        
        # Se chegou aqui, o serviço está no escopo
        break
    
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
    
    # Mensagem personalizada de confirmação - tente a API primeiro, use fallback se falhar
    try:
        confirmacao = consultar_gemini(
            f"Crie uma mensagem de confirmação de agendamento entusiasmada e personalizada para uma cliente chamada {nome_cliente} que agendou {servico} com {colaboradora} às {horario}. Mantenha a mensagem curta e amigável.",
            f"Cliente: {nome_cliente}, Serviço: {servico}",
            verificar_escopo=False
        )
    except Exception:
        confirmacao = f"Agendamento confirmado, {nome_cliente}! Seu horário para {servico} com {colaboradora} às {horario} está garantido. Estamos ansiosos para recebê-la no Bella Beauty Salon!"
    
    print(f"\n✅ {confirmacao}")


def sugestoes_e_duvidas():
    """Função unificada para lidar com sugestões e dúvidas"""
    print("\n🌟 Como posso ajudar você com cabelos e unhas hoje?")
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
    
    gosto = input("Por favor, conte-me um pouco sobre o que você está procurando para cabelo ou unhas "
                 "(ex: 'meu cabelo está danificado', 'minhas unhas quebram facilmente'): ").strip()
    
    if not gosto:
        print("⚠️ Para que eu possa sugerir o melhor serviço, preciso saber um pouco mais sobre o que você procura.")
        return
    
    # Verifica se o tema está dentro do escopo
    if not verificar_topico_permitido(gosto):
        print("⚠️ Desculpe, como assistente especializada do Bella Beauty Salon, posso ajudar apenas com "
              "assuntos relacionados a cabelos e unhas. Poderia reformular sua pergunta?")
        return
        
    prompt = f"Uma cliente do salão de beleza compartilhou a seguinte necessidade/situação: '{gosto}'. " \
             f"Sugira 2-3 serviços específicos do nosso salão (APENAS para cabelo ou unhas) que seriam ideais para ela, explicando brevemente por que cada um " \
             f"seria benéfico no caso dela. Seja específica, acolhedora e demonstre conhecimento técnico de beleza."
    
    try:
        sugestao = consultar_gemini(prompt, verificar_escopo=False)
        print("\n✨ Recomendações personalizadas para você:\n", sugestao)
    except Exception:
        # Resposta fallback baseada em palavras-chave simples no input
        print("\n✨ Com base no que você mencionou, aqui estão algumas recomendações:")
        if "danificado" in gosto.lower() or "seco" in gosto.lower() or "quebr" in gosto.lower():
            if "cabelo" in gosto.lower():
                print("1. Tratamento de hidratação profunda - Ideal para restaurar a saúde de cabelos danificados")
                print("2. Reconstrução capilar - Repõe nutrientes e fortalece a estrutura do fio")
                print("3. Corte das pontas - Remove as partes mais danificadas para um visual mais saudável")
            elif "unha" in gosto.lower():
                print("1. Tratamento fortalecedor para unhas - Ajuda a reparar unhas quebradiças")
                print("2. Manicure em gel - Proporciona proteção adicional para unhas frágeis")
                print("3. Hidratação intensiva para cutículas - Nutre a região ao redor da unha")
        else:
            print("1. Consulta personalizada com nossas especialistas - Para análise detalhada das suas necessidades")
            print("2. Pacote de tratamento completo - Cuida de todas as necessidades do seu cabelo ou unhas")
            print("3. Manutenção regular - Garante resultados duradouros e bem-estar contínuo")


def responder_duvidas():
    """Responde às dúvidas da cliente sobre os serviços e cuidados com cabelo/unhas"""
    print("❓ Em que posso ajudar? Sou especialista em cuidados com cabelo e unhas!")
    
    duvida = input("Qual é a sua dúvida sobre cabelo ou unhas? ").strip()
    
    if not duvida:
        print("⚠️ Por favor, faça sua pergunta para que eu possa ajudar.")
        return
    
    # Verifica se a dúvida está dentro do escopo
    if not verificar_topico_permitido(duvida):
        print("⚠️ Desculpe, como assistente especializada do Bella Beauty Salon, posso ajudar apenas com "
              "assuntos relacionados a cabelos e unhas. Poderia reformular sua pergunta?")
        return
    
    prompt = f"Uma cliente do salão de beleza tem a seguinte dúvida: '{duvida}'. " \
             f"Responda de forma completa, educada e informativa, demonstrando conhecimento técnico sobre tratamentos " \
             f"de beleza e cuidados com cabelo e unhas. Use linguagem acessível, mas técnica quando necessário. " \
             f"Forneça informações práticas e úteis. APENAS sugira serviços do nosso salão relacionados a cabelo e unhas " \
             f"que possam ajudar com a questão dela ou produtos para uso em casa."
    
    try:
        resposta = consultar_gemini(prompt, verificar_escopo=False)
        print("\n📝 Resposta:", resposta)
    except Exception:
        # Resposta fallback genérica
        print("\n📝 Resposta: Para responder sua pergunta sobre cuidados com cabelo e unhas da melhor forma, recomendamos uma consulta personalizada com uma de nossas especialistas. Cada caso é único e merece atenção especial. Gostaríamos de oferecer um diagnóstico preciso e recomendações específicas para suas necessidades. Podemos agendar um horário para você conversar com uma de nossas profissionais?")
    
    # Pergunta se a resposta foi útil
    util = input("\nEssa resposta foi útil para você? (Sim/Não): ").strip().lower()
    if util != "sim":
        mais_info = input("Por favor, me conte mais detalhes sobre sua dúvida de cabelo ou unhas para que eu possa ajudar melhor: ").strip()
        
        # Verifica novamente se está dentro do escopo
        if not verificar_topico_permitido(mais_info):
            print("⚠️ Desculpe, como assistente especializada do Bella Beauty Salon, posso ajudar apenas com "
                  "assuntos relacionados a cabelos e unhas. Poderia reformular sua pergunta?")
            return
            
        if mais_info:
            contexto = f"A cliente não ficou satisfeita com a resposta anterior sobre: '{duvida}'. " \
                      f"Ela adicionou as seguintes informações: '{mais_info}'. " \
                      f"Por favor, forneça uma resposta mais direcionada e específica, usando seu conhecimento especializado em cuidados com cabelo e unhas."
            
            try:
                nova_resposta = consultar_gemini(contexto, verificar_escopo=False)
                print("\n📝 Resposta atualizada:", nova_resposta)
            except Exception:
                print("\n📝 Resposta atualizada: Entendo melhor sua situação agora. Com base nesses detalhes, recomendamos que agende uma consulta com uma de nossas especialistas que poderá avaliar presencialmente e oferecer o tratamento mais adequado. Se preferir, podemos oferecer algumas dicas iniciais por telefone com uma de nossas profissionais. Gostaria de agendar um horário para atendimento personalizado?")


def verificar_api_key():
    """Verifica se a API key do Gemini está configurada"""
    if not API_KEY:
        print("⚠️ A chave de API do Gemini não foi encontrada.")
        print("Por favor, configure a variável GEMINI_API_KEY no arquivo .env")
        print("Exemplo: GEMINI_API_KEY=sua_chave_aqui")
        return False
    return True


def main():
    """Função principal do programa"""
    # Verifica se a API key existe antes de começar
    if not verificar_api_key():
        return
        
    # Verifica se o arquivo de agendamentos existe
    criar_arquivo_agendamentos_se_nao_existir()
    
    print(f"🏪 Bem-vindo ao sistema de atendimento do {NOME_SALAO}!")
    
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
            try:
                mensagem_despedida = consultar_gemini(
                    "Crie uma mensagem de despedida calorosa e breve para uma cliente do salão de beleza que está encerrando a conversa.",
                    verificar_escopo=False
                )
            except Exception:
                mensagem_despedida = "Muito obrigada por conversar conosco! Esperamos vê-la em breve no Bella Beauty Salon. Tenha um dia maravilhoso!"
                
            print(f"\n👋 {mensagem_despedida}")
            break
        else:
            print("❌ Opção inválida. Por favor, escolha uma das opções disponíveis.")


if __name__ == "__main__":
    main()