import os
import requests
import socketio
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json
import time # Importar a biblioteca time

# ====== CONFIGURAÇÕES ======
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyB9yO3LcVDD_ympsWu74qEwgeZPULoD9B0")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"
NOME_SALAO = "Salão Bella Beauty"
DB_PATH = 'salao_bella.db'
HORARIOS_DISPONIVEIS = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00", "17:00"]
COLABORADORAS = ["Ana", "Beatriz", "Carla"]
SERVICOS = {
    "cabelo": ["corte", "hidratação", "coloração", "escova", "penteado"],
    "unhas": ["manicure", "pedicure", "esmaltação", "nail design", "alongamento"],
    "estética": ["limpeza de pele", "massagem", "maquiagem", "design de sobrancelhas"]
}

# ====== BANCO DE DADOS ======
def criar_banco():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT,
            mensagem TEXT,
            resposta TEXT,
            data TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT,
            nome TEXT,
            colaboradora TEXT,
            servico TEXT,
            horario TEXT,
            data_agendamento TEXT,
            data_registro TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE,
            nome TEXT,
            ultima_visita TEXT,
            preferencias TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("[✓] Banco de dados inicializado")

def salvar_mensagem(numero, mensagem, resposta):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO mensagens (numero, mensagem, resposta, data)
        VALUES (?, ?, ?, ?)
    ''', (numero, mensagem, resposta, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

def salvar_agendamento(numero, nome, colaboradora, servico, horario, data=None):
    if not data:
        # Se não especificada, agenda para o próximo dia útil
        data = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        # Evita finais de semana
        dia_semana = datetime.strptime(data, '%Y-%m-%d').weekday()
        if dia_semana >= 5:  # 5=Sábado, 6=Domingo
            data = (datetime.now() + timedelta(days=3 if dia_semana == 5 else 2)).strftime('%Y-%m-%d')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO agendamentos (numero, nome, colaboradora, servico, horario, data_agendamento, data_registro)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (numero, nome, colaboradora, servico, horario, data, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    # Atualiza ou cria cliente
    preferencias = json.dumps({"ultimo_servico": servico, "colaboradora_preferida": colaboradora})
    cursor.execute('''
        INSERT INTO clientes (numero, nome, ultima_visita, preferencias)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(numero) DO UPDATE SET
        nome=?, ultima_visita=?, preferencias=?
    ''', (numero, nome, data, preferencias, nome, data, preferencias))

    conn.commit()
    conn.close()
    return data

def carregar_horarios_ocupados(data=None):
    if not data:
        data = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT horario, colaboradora FROM agendamentos WHERE data_agendamento = ?', (data,))
    resultados = cursor.fetchall()
    conn.close()

    # Retorna dicionário com horários ocupados por colaboradora
    horarios_ocupados = {col: [] for col in COLABORADORAS}
    for horario, colaboradora in resultados:
        if colaboradora in horarios_ocupados:
            horarios_ocupados[colaboradora].append(horario)

    return horarios_ocupados

def recuperar_cliente(numero):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT nome, ultima_visita, preferencias FROM clientes WHERE numero = ?', (numero,))
    resultado = cursor.fetchone()
    conn.close()

    if resultado:
        nome, ultima_visita, preferencias = resultado
        return {
            "nome": nome,
            "ultima_visita": ultima_visita,
            "preferencias": json.loads(preferencias) if preferencias else {}
        }
    return None

def recuperar_historico(numero, limite=3):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT mensagem, resposta, data FROM mensagens
        WHERE numero = ?
        ORDER BY data DESC LIMIT ?
    ''', (numero, limite))
    dados = cursor.fetchall()
    conn.close()
    return dados

def recuperar_agendamentos(numero):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Busca apenas agendamentos futuros
    hoje = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT colaboradora, servico, horario, data_agendamento
        FROM agendamentos
        WHERE numero = ? AND data_agendamento >= ?
        ORDER BY data_agendamento ASC, horario ASC
    ''', (numero, hoje))
    dados = cursor.fetchall()
    conn.close()
    return dados

# ====== INTELIGÊNCIA (GEMINI) ======
def perguntar_gemini(pergunta, contexto=""):
    try:
        # Personalidade da assistente
        prompt_sistema = """
        Você é Bella, a assistente virtual do Salão Bella Beauty. Você é extremamente educada,
        compreensiva, delicada e especialista em cabelos e unhas. Sua personalidade é:

        - Acolhedora e calorosa, sempre tratando as clientes pelo nome
        - Especialista em tratamentos capilares e cuidados com unhas
        - Detalhista ao dar dicas de beleza, sempre com embasamento
        - Paciente e prestativa com todas as dúvidas
        - Discreta e elegante na forma de se comunicar
        - Usa emojis com moderação para transmitir emoções positivas (💖✨💅👩‍🦰)

        Você APENAS responde sobre assuntos relacionados a:
        - Cuidados com cabelo (cortes, tratamentos, produtos, coloração)
        - Cuidados com unhas (manicure, pedicure, esmaltes, técnicas)
        - Serviços oferecidos pelo salão
        - Dicas de beleza específicas dessas áreas
        - Informações solicitadas do menu de Informações (opção 6)

        Para qualquer pergunta fora dessas áreas ou que não se encaixe nos fluxos do menu (agendamento, dicas, informações), gentilmente redirecione a cliente para o menu
        principal ou sugira falar com uma atendente humana.

        Suas respostas devem ser detalhadas quando dando dicas, mas concisas e claras quando
        orientando sobre procedimentos do salão. Mantenha um tom profissional e acolhedor.
        """

        if contexto:
            prompt_completo = f"{prompt_sistema}\n\nContexto sobre a cliente: {contexto}\n\nPergunta da cliente: {pergunta}"
        else:
            prompt_completo = f"{prompt_sistema}\n\nPergunta da cliente: {pergunta}"

        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [
                {"parts": [{"text": prompt_completo}]}
            ],
            "generationConfig": {
                "temperature": 0.2,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1024,
            }
        }

        response = requests.post(URL, headers=headers, json=data, timeout=60)
        if response.status_code == 200:
            resposta_json = response.json()
            # Verifica se a chave 'candidates' e as subchaves existem antes de acessar
            if 'candidates' in resposta_json and resposta_json['candidates'] and \
               'content' in resposta_json['candidates'][0] and \
               'parts' in resposta_json['candidates'][0]['content'] and \
               resposta_json['candidates'][0]['content']['parts']:
                return resposta_json['candidates'][0]['content']['parts'][0]['text']
            else:
                 print(f"[Erro API] Resposta inesperada da Gemini: {resposta_json}")
                 return "✨ Recebi uma resposta inesperada da inteligência artificial. Posso ajudar de outra forma?"
        else:
            print(f"[Erro API] Status: {response.status_code}, Resposta: {response.text}")
            return "✨ Estou com dificuldades técnicas no momento. Poderia tentar novamente em instantes?"
    except requests.exceptions.Timeout:
         print(f"[Erro] Timeout na API Gemini")
         return "✨ A inteligência artificial demorou muito para responder. Poderia tentar novamente em instantes?"
    except Exception as e:
        print(f"[Erro] Falha na API Gemini: {e}")
        return "✨ Desculpe, não consegui processar sua solicitação. Posso ajudar de outra forma?"

# ====== WHATSAPP ======
def enviar_mensagem(id_sessao, numero, mensagem):
    url = 'http://localhost:3000/enviarMensagem'
    payload = {
        'idSessao': id_sessao,
        'numero': numero,
        'mensagem': mensagem
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
             print(f"[{datetime.now()}] Mensagem enviada para {numero}: {mensagem[:50]}...") # Log de sucesso
        else:
            print(f"[{datetime.now()}] [Erro] Envio falhou: Status {response.status_code}, Resposta: {response.text}")
    except Exception as e:
        print(f"[{datetime.now()}] [Erro] Falha ao enviar: {e}")

# Função para interpretar a intenção da mensagem (simplificada para os exemplos do menu)
def interpretar_mensagem(msg):
    msg = msg.lower()
    if any(p in msg for p in ['agendar', 'horário', 'agenda', 'marcar']):
        return 'agendamento'
    # A lógica para 'dica' será mais focada em palavras-chave no else final do menu principal
    # if any(p in msg for p in ['unha', 'cabelo', 'hidratação', 'manicure', 'dica', 'conselho']):
    #     return 'dica'
    if any(p in msg for p in ['cancelar', 'desmarcar', 'reagendar']):
        return 'cancelamento'
    if any(p in msg for p in ['atendente', 'humano', 'pessoa', 'gerente']):
        return 'atendente'
    if any(p in msg for p in ['informações', 'informacoes', 'info', 'saber mais']):
        return 'informacoes' # Nova intenção
    return None

# ====== BOT PRINCIPAL (CORRIGIDO) ======
def ouvir_mensagens(id_sessao):
    sio = socketio.Client()
    estados = {}
    global tentativas_reconexao
    tentativas_reconexao = 0 # Inicializa tentativas_reconexao aqui
    max_tentativas = 5

    @sio.event
    def connect():
        print(f"[{datetime.now()}] ✅ Bot conectado à sessão {id_sessao}")
        tentativas_reconexao = 0 # Resetar tentativas ao conectar

    @sio.event
    def connect_error(data):
        print(f"[{datetime.now()}] ❌ Erro de conexão: {data}")

    @sio.event
    def disconnect():
        tentativas_reconexao += 1
        print(f"[{datetime.now()}] ⚠ Desconectado. Tentativa {tentativas_reconexao}/{max_tentativas}")

        if tentativas_reconexao <= max_tentativas:
            print("Tentando reconectar em 5 segundos...")
            time.sleep(5)
            try:
                sio.connect('http://localhost:3000')
            except Exception as e:
                 print(f"[{datetime.now()}] Falha na reconexão inicial: {e}")
                 # Pode adicionar um tempo de espera maior ou logica de retry mais sofisticada aqui
        else:
            print("Número máximo de tentativas alcançado. Encerrando...")


    @sio.event
    def novaMensagem(data):
        if data['idSessao'] != id_sessao:
            return

        numero = data['from'].replace('@c.us', '')
        msg = data['body'].strip()
        msg_lower = msg.lower()
        resposta = ""

        print(f"[{datetime.now()}] Mensagem de {numero}: {msg}") # Log para depuração

        # Recupera informações do cliente, se existir
        cliente = recuperar_cliente(numero)
        contexto_cliente = ""
        nome_cliente = cliente["nome"] if cliente else "querida cliente" # Define nome para saudações

        if cliente:
            contexto_cliente = f"Nome: {cliente['nome']}, Última visita: {cliente['ultima_visita']}"
            if cliente['preferencias']:
                contexto_cliente += f", Preferências: {json.dumps(cliente['preferencias'])}" # Serializa preferencias para o contexto


        # Inicializa estado se for novo cliente ou limpa se for 'menu' ou após inatividade
        # Adicionada lógica para tratar a primeira mensagem do dia ou cliente novo
        tempo_inatividade_limite = 60*60 # 1 hora em segundos
        if numero not in estados or 'ultima_interacao' not in estados[numero] or \
           (datetime.now() - estados[numero]['ultima_interacao']).total_seconds() > tempo_inatividade_limite or \
           msg_lower == 'menu' or msg_lower in ['oi', 'olá', 'ola']:

             # Só envia saudação e menu se for realmente a primeira mensagem ou após um longo tempo, ou se o cliente explicitamente pediu o menu
             if numero not in estados or 'ultima_interacao' not in estados[numero] or \
                (datetime.now() - estados[numero]['ultima_interacao']).total_seconds() > tempo_inatividade_limite or \
                msg_lower in ['oi', 'olá', 'ola']: # Adiciona saudação para 'oi'/'olá' mesmo que não tenha passado o tempo limite

                  saudacao = f"Olá {nome_cliente}! Que bom ver você aqui no {NOME_SALAO}! 💖"
                  enviar_mensagem(id_sessao, numero, saudacao)
                  # Pequena pausa para a saudação ir antes do menu
                  time.sleep(0.5) # Pausa menor

             resposta = (
                 f"🌸 Olá, {nome_cliente}! Bem-vinda ao {NOME_SALAO} 🌸\n\n"
                 "Como posso ajudar hoje?\n\n"
                 "1 - Agendar horário 📅\n"
                 "2 - Dicas de beleza ✨\n"
                 "3 - Falar com uma atendente 👩‍💼\n"
                 "4 - Ver meus agendamentos 🗓\n"
                 "5 - Cancelar agendamento ❌\n"
                 "6 - Informações** ℹ️\n\n" 
                 "Ou se preferir, me conte diretamente o que precisa! 😊"
             )
             estados[numero] = {"etapa": None, "ultima_interacao": datetime.now()} # Reseta a etapa ao mostrar o menu principal e registra o tempo

        else:
            etapa = estados[numero]["etapa"]
            estados[numero]["ultima_interacao"] = datetime.now() # Atualiza o tempo da última interação

            # ====== LÓGICA DO MENU PRINCIPAL ======
            # Note: A lógica para o 'menu' está acima, então este bloco só trata opções diretas ou o fluxo de etapas
            if etapa is None:
                if msg_lower == '1' or interpretar_mensagem(msg) == 'agendamento':
                    if cliente:
                        resposta = f"Vamos agendar seu horário, {cliente['nome']}! Com qual colaboradora você prefere se atender? Temos: {', '.join(COLABORADORAS)}."
                        estados[numero] = {
                            "etapa": "colaboradora",
                            "nome": cliente["nome"] # Usa nome do cliente existente
                        }
                    else:
                        resposta = "Vamos agendar seu horário! Qual o seu nome?"
                        estados[numero]["etapa"] = "nome"

                elif msg_lower == '2' or interpretar_mensagem(msg) == 'dica': # Manter interpretar_mensagem para 'dica' aqui para cobrir casos iniciais
                     resposta = "✨ Adoraria te dar dicas personalizadas! Me conte o que você gostaria de saber sobre cabelos ou unhas. Por exemplo:\n\n- Como hidratar cabelos cacheados\n- Cuidados com unhas fracas\n- Produtos para cabelos tingidos\n\nDigite 'menu' para voltar."
                     estados[numero]["etapa"] = "preferencia_dica"

                elif msg_lower == '3' or interpretar_mensagem(msg) == 'atendente':
                    resposta = f"📞 Uma de nossas atendentes entrará em contato com você em breve, {nome_cliente}. Enquanto isso, posso responder suas dúvidas sobre nossos serviços ou agendamentos!"
                    # Pode adicionar lógica aqui para notificar um atendente real
                    estados[numero]["etapa"] = None # Finaliza esta interação

                elif msg_lower == '4':
                    agendamentos = recuperar_agendamentos(numero)
                    if agendamentos:
                        resposta = "🗓 Seus próximos agendamentos:\n\n"
                        for col, serv, hora, data in agendamentos:
                            data_formatada = datetime.strptime(data, '%Y-%m-%d').strftime('%d/%m/%Y')
                            resposta += f"• {data_formatada} às {hora} - {serv.title()} com {col}\n"
                        resposta += "\nPara cancelar algum, digite '5'.\nDigite 'menu' para voltar."
                    else:
                        resposta = "Você não possui agendamentos futuros. Que tal marcar um horário? Digite '1' para agendar!\nDigite 'menu' para voltar."
                    estados[numero]["etapa"] = None # Finaliza esta interação

                elif msg_lower == '5' or interpretar_mensagem(msg) == 'cancelamento':
                    agendamentos = recuperar_agendamentos(numero) # Verifica se tem agendamentos para dar a instrução
                    if agendamentos:
                         resposta = "Para cancelar ou reagendar um agendamento, entre em contato com nossa recepção pelo telefone (75) 9999-8888. Por medidas de segurança e para te dar o melhor suporte, preferimos fazer isso com atendimento pessoal. 🙏\nDigite 'menu' para voltar."
                    else:
                         resposta = "Você não possui agendamentos para cancelar. Deseja marcar um horário? Digite '1'.\nDigite 'menu' para voltar."
                    estados[numero]["etapa"] = None # Finaliza esta interação

                # ====== NOVA OPÇÃO DE MENU: INFORMAÇÕES ======
                elif msg_lower == '6' or interpretar_mensagem(msg) == 'informacoes': # Usa a função interpretar_mensagem
                    resposta = (
                        "ℹ️ **Informações do Salão Bella Beauty**\n\n"
                        "Por favor, escolha uma opção digitando o número:\n\n"
                        "2.1 - Consultar saldo do pacote 📦\n"
                        "2.2 - Pedir informações sobre serviços ❓\n"
                        "2.3 - Consultar serviços disponíveis ✨\n"
                        "2.4 - Consultar pacotes de beleza 🎁\n"
                        "2.5 - Ver preços por tamanho do cabelo 📏\n\n"
                        "Ou digite 'menu' para voltar ao menu principal."
                    )
                    estados[numero]["etapa"] = "submenu_informacoes" # Muda para a nova etapa do submenu

                else:
                     # Resposta padrão se não reconhecer a opção no menu principal
                     # Antes de responder, verifica se é uma pergunta que a Gemini pode responder (dicas de beleza)
                     if any(palavra in msg_lower for palavra in ["cabelo", "unha", "hidrat", "corte", "tinta", "esmalte", "escova", "volume", "dica", "qual melhor", "cuidados com", "produto"]):
                          # Usa o contexto do cliente para personalizar a resposta
                          dica = perguntar_gemini(msg, contexto_cliente)
                          resposta = f"✨ {dica}\n\nPosso ajudar com mais alguma coisa? Digite 'menu' para ver as opções principais."
                          estados[numero]["etapa"] = None # Assume que a interação de dica finalizou
                     else:
                          resposta = (
                              f"💖 Olá, {nome_cliente}! Estou aqui para ajudar com dicas de beleza e agendamentos para cabelos e unhas! "
                              f"Não entendi sua mensagem. Digite 'menu' para ver todas as opções disponíveis."
                          )
                          # Mantém a etapa como None, aguardando nova interação ou 'menu'


            # ====== LÓGICA DO SUBMENU INFORMAÇÕES ======
            elif etapa == "submenu_informacoes":
                 if msg_lower == '2.1':
                     # Lógica para consultar saldo do pacote
                     # >>> NECESSITA DE DADOS DE PACOTES ADQUIRIDOS PELO CLIENTE <<<
                     resposta = (
                         "📦 **Saldo do seu pacote:**\n\n"
                         "Para consultar o saldo dos seus pacotes contratados, por favor, entre em contato diretamente com nossa recepção pelo telefone (11) 9999-8888 ou visite-nos no salão. Precisamos confirmar alguns dados para garantir a sua segurança. 🙏\n\n"
                         "Digite o número para escolher outra opção de informação ou 'menu' para voltar."
                     )
                     # estados[numero]["etapa"] = "submenu_informacoes" # Fica na mesma etapa para permitir outras opções do submenu

                 elif msg_lower == '2.2':
                     # Lógica para pedir informações sobre serviços (usando Gemini)
                     resposta = "❓ Certo! Sobre qual serviço você gostaria de saber mais? Pode perguntar!\nDigite 'menu' para voltar."
                     estados[numero]["etapa"] = "info_servico_pergunta" # Muda para a etapa de pergunta sobre serviço

                 elif msg_lower == '2.3':
                     # Lógica para consultar serviços disponíveis (usando o dicionário SERVICOS)
                     servicos_txt = "✨ **Serviços Disponíveis no Bella Beauty:**\n\n"
                     for categoria, lista in SERVICOS.items():
                         servicos_txt += f"• {categoria.title()}: {', '.join([s.title() for s in lista])}\n" # Formata com Title Case
                     servicos_txt += "\nPara agendar, digite '1'.\nDigite o número para escolher outra opção de informação ou 'menu' para voltar."
                     resposta = servicos_txt
                     # estados[numero]["etapa"] = "submenu_informacoes" # Fica na mesma etapa

                 elif msg_lower == '2.4':
                     # Lógica para consultar pacotes de beleza
                     # >>> NECESSITA DE DADOS DE PACOTES DISPONÍVEIS <<<
                     resposta = (
                         "🎁 **Nossos Pacotes de Beleza (Exemplos):**\n\n"
                         "• **Pacote Bronze:** 2 Escovas + 1 Hidratação (Validade: 3 meses)\n"
                         "• **Pacote Prata:** 4 Escovas + 2 Pranchas + 2 Hidratações (Validade: 6 meses)\n"
                         "• **Pacote Ouro:** Serviços ilimitados por 1 mês (Consulte as regras detalhadas na recepção)\n\n"
                         "Para saber os preços ou montar um pacote personalizado, entre em contato conosco! 😉\n\n"
                         "Digite o número para escolher outra opção de informação ou 'menu' para voltar."
                     )
                     # estados[numero]["etapa"] = "submenu_informacoes" # Fica na mesma etapa

                 elif msg_lower == '2.5':
                     # Lógica para ver preços por tamanho do cabelo
                     # >>> NECESSITA DE TABELA DE PREÇOS POR TAMANHO <<<
                     resposta = (
                         "📏 **Preços de Prancha por Tamanho do Cabelo:**\n\n"
                         "(Valores aproximados, podem variar levemente dependendo da textura e volume)\n\n"
                         "• Cabelo Curto: R$ 30,00\n"
                         "• Cabelo Médio: R$ 40,00\n"
                         "• Cabelo Longo: R$ 50,00\n\n"
                         "Para outros serviços, por favor, consulte a lista completa de serviços (opção 2.3) ou entre em contato. 😉\n\n"
                         "Digite o número para escolher outra opção de informação ou 'menu' para voltar."
                     )
                     # estados[numero]["etapa"] = "submenu_informacoes" # Fica na mesma etapa

                 elif msg_lower == 'menu':
                      resposta = (
                         f"🌸 Olá, {nome_cliente}! Bem-vinda de volta ao menu principal do {NOME_SALAO} 🌸\n\n"
                         "Como posso ajudar hoje?\n\n"
                         "1 - Agendar horário 📅\n"
                         "2 - Dicas de beleza ✨\n"
                         "3 - Falar com uma atendente 👩‍💼\n"
                         "4 - Ver meus agendamentos 🗓\n"
                         "5 - Cancelar agendamento ❌\n"
                         "**6 - Informações** ℹ️\n\n"
                         "Ou se preferir, me conte diretamente o que precisa! 😊"
                     )
                      estados[numero]["etapa"] = None # Volta para a etapa principal

                 else:
                     # Resposta para entrada inválida no submenu de informações
                     resposta = (
                         "🤔 Opção inválida no menu de Informações. Por favor, digite o número correspondente à opção desejada:\n\n"
                         "2.1 - Consultar saldo do pacote 📦\n"
                         "2.2 - Pedir informações sobre serviços ❓\n"
                         "2.3 - Consultar serviços disponíveis ✨\n"
                         "2.4 - Consultar pacotes de beleza 🎁\n"
                         "2.5 - Ver preços por tamanho do cabelo 📏\n\n"
                         "Ou digite 'menu' para voltar ao menu principal."
                     )
                     # estados[numero]["etapa"] = "submenu_informacoes" # Fica na mesma etapa para nova tentativa


            # ====== LÓGICA PARA TRATAR PERGUNTA DE DICA (ETAPA 'preferencia_dica') ======
            elif etapa == "preferencia_dica":
                if msg_lower == 'menu':
                     resposta = (
                        f"🌸 Ok, {nome_cliente}! Voltando ao menu principal. Como posso ajudar agora? 🌸\n\n"
                        "1 - Agendar horário 📅\n"
                        "2 - Dicas de beleza ✨\n"
                        "3 - Falar com uma atendente 👩‍💼\n"
                        "4 - Ver meus agendamentos 🗓\n"
                        "5 - Cancelar agendamento ❌\n"
                        "**6 - Informações** ℹ️\n\n"
                        "Ou se preferir, me conte diretamente o que precisa! 😊"
                     )
                     estados[numero]["etapa"] = None
                else:
                    # Usa o contexto do cliente para personalizar a resposta
                    dica = perguntar_gemini(msg, contexto_cliente)
                    resposta = f"✨ {dica}\n\nPosso ajudar com mais alguma dica? Ou digite 'menu' para voltar."
                    # Mantém na mesma etapa para permitir mais perguntas sobre dicas,
                    # ou pode mudar para None se quiser que ele volte ao menu principal após uma dica.
                    # Vamos manter na mesma etapa por enquanto para um fluxo de "dicas" mais natural.
                    # estados[numero]["etapa"] = "preferencia_dica" # Fica na mesma etapa


            # ====== LÓGICA PARA PERGUNTA SOBRE SERVIÇO NO SUBMENU (ETAPA 'info_servico_pergunta') ======
            elif etapa == "info_servico_pergunta":
                if msg_lower == 'menu':
                     resposta = (
                        f"🌸 Ok, {nome_cliente}! Voltando ao menu principal. Como posso ajudar agora? 🌸\n\n"
                        "1 - Agendar horário 📅\n"
                        "2 - Dicas de beleza ✨\n"
                        "3 - Falar com uma atendente 👩‍💼\n"
                        "4 - Ver meus agendamentos 🗓\n"
                        "5 - Cancelar agendamento ❌\n"
                        "**6 - Informações** ℹ️\n\n"
                        "Ou se preferir, me conte diretamente o que precisa! 😊"
                     )
                     estados[numero]["etapa"] = None
                else:
                    # Passa a pergunta do usuário para a Gemini com contexto
                    dica = perguntar_gemini(msg, contexto_cliente)
                    resposta = f"✨ {dica}\n\nEspero ter ajudado! Posso tirar mais alguma dúvida sobre serviços? Ou digite o número para escolher outra opção de informação ou 'menu' para voltar."
                    # Após responder, pode-se optar por voltar ao submenu de informações ou ficar nesta etapa aguardando mais perguntas sobre serviços.
                    # Vamos voltar para o submenu para manter a navegação clara.
                    estados[numero]["etapa"] = "submenu_informacoes" # Volta para o submenu de informações


            # ====== LÓGICA DO FLUXO DE AGENDAMENTO (já existente e com 'menu' adicionado) ======
            # As etapas 'nome', 'colaboradora', 'servico', 'horario' continuam aqui
            # Certifique-se de que estas etapas validam as entradas E ofereçam a opção de digitar 'menu' para sair
            elif etapa == "nome":
                 if msg_lower == 'menu':
                      resposta = (
                         f"🌸 Ok, {nome_cliente}! Voltando ao menu principal. Como posso ajudar agora? 🌸\n\n"
                         "1 - Agendar horário 📅\n"
                         "2 - Dicas de beleza ✨\n"
                         "3 - Falar com uma atendente 👩‍💼\n"
                         "4 - Ver meus agendamentos 🗓\n"
                         "5 - Cancelar agendamento ❌\n"
                         "**6 - Informações** ℹ️\n\n"
                         "Ou se preferir, me conte diretamente o que precisa! 😊"
                     )
                      estados[numero]["etapa"] = None
                 else:
                      estados[numero]["nome"] = msg.title()
                      resposta = f"Ótimo, {estados[numero]['nome']}! Com qual de nossas profissionais você gostaria de se atender? Temos: {', '.join(COLABORADORAS)}.\nDigite 'menu' para voltar."
                      estados[numero]["etapa"] = "colaboradora"

            elif etapa == "colaboradora":
                 if msg_lower == 'menu':
                      resposta = (
                         f"🌸 Ok, {nome_cliente}! Voltando ao menu principal. Como posso ajudar agora? 🌸\n\n"
                         "1 - Agendar horário 📅\n"
                         "2 - Dicas de beleza ✨\n"
                         "3 - Falar com uma atendente 👩‍💼\n"
                         "4 - Ver meus agendamentos 🗓\n"
                         "5 - Cancelar agendamento ❌\n"
                         "**6 - Informações** ℹ️\n\n"
                         "Ou se preferir, me conte diretamente o que precisa! 😊"
                     )
                      estados[numero]["etapa"] = None
                 else:
                      nome_colaboradora = msg.title()
                      colaboradora_encontrada = None
                      for col in COLABORADORAS:
                           if col.startswith(nome_colaboradora):
                               colaboradora_encontrada = col
                               break

                      if colaboradora_encontrada:
                           estados[numero]["colaboradora"] = colaboradora_encontrada
                           servicos_txt = ""
                           for categoria, lista in SERVICOS.items():
                               servicos_txt += f"• {categoria.title()}: {', '.join([s.title() for s in lista])}\n" # Formata com Title Case

                           resposta = f"Excelente escolha! A {colaboradora_encontrada} é especialista. Qual serviço você deseja?\n\n{servicos_txt}\nDigite 'menu' para voltar."
                           estados[numero]["etapa"] = "servico"
                      else:
                           resposta = f"⚠ Não encontrei essa profissional em nossa equipe. Por favor, escolha entre: {', '.join(COLABORADORAS)}.\nDigite 'menu' para voltar."
                           # Mantém na mesma etapa

            elif etapa == "servico":
                 if msg_lower == 'menu':
                      resposta = (
                         f"🌸 Ok, {nome_cliente}! Voltando ao menu principal. Como posso ajudar agora? 🌸\n\n"
                         "1 - Agendar horário 📅\n"
                         "2 - Dicas de beleza ✨\n"
                         "3 - Falar com uma atendente 👩‍💼\n"
                         "4 - Ver meus agendamentos 🗓\n"
                         "5 - Cancelar agendamento ❌\n"
                         "**6 - Informações** ℹ️\n\n"
                         "Ou se preferir, me conte diretamente o que precisa! 😊"
                     )
                      estados[numero]["etapa"] = None
                 else:
                      servico = msg.lower()
                      estados[numero]["servico"] = servico

                      if "não sei" in servico or "indecisa" in servico:
                           contexto = f"Cliente: {estados[numero]['nome']}, Colaboradora escolhida: {estados[numero]['colaboradora']}"
                           sugestao = perguntar_gemini("Sugira serviços de salão personalizados para uma cliente indecisa, focando em cabelos e unhas.", contexto)
                           resposta = f"💡 {sugestao}\n\nDiga-me qual serviço você escolheu para continuarmos o agendamento, ou digite 'menu' para voltar."
                           estados[numero]["etapa"] = "servico"
                      else:
                           # Verificar disponibilidade
                           data_agenda = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                           horarios_ocupados = carregar_horarios_ocupados(data_agenda)
                           colaboradora = estados[numero]["colaboradora"]

                           horarios_livres = [h for h in HORARIOS_DISPONIVEIS if h not in horarios_ocupados.get(colaboradora, [])]

                           if horarios_livres:
                                data_formatada = datetime.strptime(data_agenda, '%Y-%m-%d').strftime('%d/%m/%Y')
                                resposta = f"Para {servico} com {colaboradora} em {data_formatada}, temos estes horários disponíveis:\n\n"
                                # Cria um dicionário para mapear números aos horários
                                horarios_numerados = {str(i+1): h for i, h in enumerate(horarios_livres)}
                                # Exibe os horários numerados
                                for num, horario in horarios_numerados.items():
                                    resposta += f"{num} - {horario}\n"
                                resposta += "\nDigite o número do horário desejado. Digite 'menu' para voltar."

                                estados[numero]["horarios_livres"] = horarios_livres
                                estados[numero]["horarios_numerados"] = horarios_numerados
                                estados[numero]["data_agenda"] = data_agenda
                                estados[numero]["etapa"] = "horario"
                           else:
                                # Tenta o próximo dia útil
                                data_agenda = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
                                horarios_ocupados = carregar_horarios_ocupados(data_agenda)
                                horarios_livres = [h for h in HORARIOS_DISPONIVEIS if h not in horarios_ocupados.get(colaboradora, [])]

                                data_formatada = datetime.strptime(data_agenda, '%Y-%m-%d').strftime('%d/%m/%Y')
                                resposta = f"Para amanhã, a agenda da {colaboradora} está completa. Para {data_formatada}, temos:\n\n"
                                # Cria um dicionário para mapear números aos horários
                                horarios_numerados = {str(i+1): h for i, h in enumerate(horarios_livres)}
                                # Exibe os horários numerados
                                for num, horario in horarios_numerados.items():
                                    resposta += f"{num} - {horario}\n"
                                resposta += "\nDigite o número do horário desejado. Digite 'outro dia' para verificar outras datas, ou digite 'menu' para voltar."

                                estados[numero]["horarios_livres"] = horarios_livres
                                estados[numero]["horarios_numerados"] = horarios_numerados
                                estados[numero]["data_agenda"] = data_agenda
                                estados[numero]["etapa"] = "horario"

            elif etapa == "horario":
                if msg_lower == 'menu':
                     resposta = (
                        f"🌸 Ok, {nome_cliente}! Voltando ao menu principal. Como posso ajudar agora? 🌸\n\n"
                        "1 - Agendar horário 📅\n"
                        "2 - Dicas de beleza ✨\n"
                        "3 - Falar com uma atendente 👩‍💼\n"
                        "4 - Ver meus agendamentos 🗓\n"
                        "5 - Cancelar agendamento ❌\n"
                        "**6 - Informações** ℹ️\n\n"
                        "Ou se preferir, me conte diretamente o que precisa! 😊"
                     )
                     estados[numero]["etapa"] = None
                else:
                     escolha = msg.lower()

                     if "outro dia" in escolha:
                         data_agenda = (datetime.strptime(estados[numero]["data_agenda"], '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
                         horarios_ocupados = carregar_horarios_ocupados(data_agenda)
                         colaboradora = estados[numero]["colaboradora"]
                         horarios_livres = [h for h in HORARIOS_DISPONIVEIS if h not in horarios_ocupados.get(colaboradora, [])]

                         data_formatada = datetime.strptime(data_agenda, '%Y-%m-%d').strftime('%d/%m/%Y')
                         resposta = f"Para {data_formatada}, temos os seguintes horários:\n\n"
                         # Cria um dicionário para mapear números aos horários
                         horarios_numerados = {str(i+1): h for i, h in enumerate(horarios_livres)}
                         # Exibe os horários numerados
                         for num, horario in horarios_numerados.items():
                             resposta += f"{num} - {horario}\n"
                         resposta += "\nDigite o número do horário desejado. Digite 'outro dia' para verificar outras datas ou 'menu' para voltar."

                         estados[numero]["horarios_livres"] = horarios_livres
                         estados[numero]["horarios_numerados"] = horarios_numerados
                         estados[numero]["data_agenda"] = data_agenda
                         # Mantém a mesma etapa

                     elif escolha in estados[numero]["horarios_numerados"]:
                         horario = estados[numero]["horarios_numerados"][escolha]

                         dados = estados[numero]
                         data_agendada = salvar_agendamento(
                              numero,
                              dados["nome"],
                              dados["colaboradora"],
                              dados["servico"],
                              horario,
                              dados["data_agenda"]
                         )

                         data_formatada = datetime.strptime(data_agendada, '%Y-%m-%d').strftime('%d/%m/%Y')

                         servico_confirmado = dados["servico"].lower()
                         if "unha" in servico_confirmado or "manicure" in servico_confirmado or "pedicure" in servico_confirmado:
                              dica_adicional = "Lembre-se de vir com as unhas limpas, sem esmalte anterior para melhores resultados! 💅"
                         elif "cabelo" in servico_confirmado or "corte" in servico_confirmado or "hidrat" in servico_confirmado:
                              dica_adicional = "Recomendamos vir com o cabelo lavado apenas se for corte. Para outros procedimentos, o ideal é vir com o cabelo natural. 👩‍🦰"
                         else:
                              dica_adicional = "Estamos ansiosas para te receber! ✨"

                         resposta = (
                              f"✅ Agendamento confirmado!\n\n"
                              f"• Data: {data_formatada}\n"
                              f"• Horário: {horario}\n"
                              f"• Serviço: {dados['servico']}\n"
                              f"• Profissional: {dados['colaboradora']}\n\n"
                              f"{dica_adicional}\n\n"
                              f"Aguardamos você, {dados['nome']}! Caso precise remarcar, é só enviar 'cancelar agendamento'. 💖\nDigite 'menu' para voltar."
                         )

                         estados[numero] = {"etapa": None, "ultima_interacao": datetime.now()} # Reseta o estado e registra a interação
                     else:
                         horarios_numerados = estados[numero]["horarios_numerados"]
                         resposta = f"⚠ Opção inválida. Por favor, escolha um número entre 1 e {len(horarios_numerados)}.\n\n"
                         for num, horario in horarios_numerados.items():
                             resposta += f"{num} - {horario}\n"
                         resposta += "\nDigite 'outro dia' para verificar outras datas ou 'menu' para voltar."


        # Envia e salva a mensagem
        if resposta:
            enviar_mensagem(id_sessao, numero, resposta)
            salvar_mensagem(numero, msg, resposta) # Salva a interação


    # Tenta conectar
    try:
        print(f"[{datetime.now()}] Conectando ao servidor Socket.IO...")
        sio.connect('http://localhost:3000')
        sio.wait()
    except socketio.exceptions.ConnectionError as e:
        print(f"[{datetime.now()}] ❌ Erro de conexão Socket.IO: {e}")
        # A lógica de reconexão já está no @sio.event('disconnect')
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Erro inesperado ao iniciar Socket.IO: {e}")
        # Em caso de erro não tratado na conexão inicial, tenta reconectar
        if tentativas_reconexao <= max_tentativas:
             print(f"[{datetime.now()}] Tentando reconectar em 5 segundos...")
             time.sleep(5)
             ouvir_mensagens(id_sessao) # Chama a função novamente para tentar reconectar
        else:
             print(f"[{datetime.now()}] Número máximo de tentativas de reconexão alcançado na inicialização.")


# ====== EXECUÇÃO ======
def main():
    criar_banco()
    print(f"[{datetime.now()}] 🌸 Iniciando Bella Beauty Bot 🌸")
    # Certifique-se de que esta ID de sessão está correta para sua instância do Venom Bot ou similar
    id_sessao = '8113' # <-- Verifique se esta ID de sessão está correta
    try:
        ouvir_mensagens(id_sessao)
    except KeyboardInterrupt:
        print("\n[✓] Bot encerrado pelo usuário")
    except Exception as e:
        print(f"[Erro Fatal] {e}")
        import traceback
        traceback.print_exc() # Imprime o traceback para ajudar na depuração
        print("Tentando reiniciar em 10 segundos...")
        time.sleep(10)
        main() # Tenta reiniciar em caso de erro fatal

if __name__ == "__main__": # <-- CORRIGIDO
    main()