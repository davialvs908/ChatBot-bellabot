import os
import requests
import socketio
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json

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
        
        Para qualquer pergunta fora dessas áreas, gentilmente redirecione a cliente para o menu
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
            return resposta_json['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"[Erro API] Status: {response.status_code}, Resposta: {response.text}")
            return "✨ Estou com dificuldades técnicas no momento. Poderia tentar novamente em instantes?"
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
        if response.status_code != 200:
            print(f"[Erro] Envio falhou: Status {response.status_code}")
    except Exception as e:
        print(f"[Erro] Falha ao enviar: {e}")

def interpretar_mensagem(msg):
    msg = msg.lower()
    if any(p in msg for p in ['agendar', 'horário', 'agenda', 'marcar']):
        return 'agendamento'
    if any(p in msg for p in ['unha', 'cabelo', 'hidratação', 'manicure', 'dica', 'conselho']):
        return 'dica'
    if any(p in msg for p in ['cancelar', 'desmarcar', 'reagendar']):
        return 'cancelamento'
    if any(p in msg for p in ['atendente', 'humano', 'pessoa', 'gerente']):
        return 'atendente'
    return None

# ====== BOT PRINCIPAL ======
def ouvir_mensagens(id_sessao):
    sio = socketio.Client()
    estados = {}
    tentativas_reconexao = 0
    max_tentativas = 5
    
    @sio.event
    def connect():
        print(f"[{datetime.now()}] ✅ Bot conectado à sessão {id_sessao}")
        global tentativas_reconexao
        tentativas_reconexao = 0
    
    @sio.event
    def connect_error(data):
        print(f"[{datetime.now()}] ❌ Erro de conexão: {data}")
        
    @sio.event
    def disconnect():
        global tentativas_reconexao
        tentativas_reconexao += 1
        print(f"[{datetime.now()}] ⚠️ Desconectado. Tentativa {tentativas_reconexao}/{max_tentativas}")
        
        if tentativas_reconexao <= max_tentativas:
            print("Tentando reconectar em 5 segundos...")
            time.sleep(5)
            sio.connect('http://localhost:3000')
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
        
        # Recupera informações do cliente, se existir
        cliente = recuperar_cliente(numero)
        contexto_cliente = ""
        if cliente:
            contexto_cliente = f"Nome: {cliente['nome']}, Última visita: {cliente['ultima_visita']}"
            if cliente['preferencias']:
                contexto_cliente += f", Preferências: {cliente['preferencias']}"

        # Inicializa estado se for novo cliente
        if numero not in estados:
            estados[numero] = {"etapa": None}
            if cliente:
                saudacao = f"Olá {cliente['nome']}! Que bom ver você novamente no {NOME_SALAO}! 💖"
                enviar_mensagem(id_sessao, numero, saudacao)

        etapa = estados[numero]["etapa"]

        # MENU PRINCIPAL
        if msg_lower == 'menu' or msg_lower == 'oi' or msg_lower == 'olá' or msg_lower == 'ola':
            nome_cliente = cliente["nome"] if cliente else "querida cliente"
            resposta = (
                f"🌸 Olá, {nome_cliente}! Bem-vinda ao {NOME_SALAO} 🌸\n\n"
                "Como posso ajudar hoje?\n\n"
                "1 - Agendar horário 📅\n"
                "2 - Dicas de beleza 💅\n"
                "3 - Falar com uma atendente 👩‍💼\n"
                "4 - Ver meus agendamentos 🗓️\n"
                "5 - Cancelar agendamento ❌\n\n"
                "Ou se preferir, me conte diretamente o que precisa! 😊"
            )
            estados[numero] = {"etapa": None}

        # AGENDAMENTO INICIAL
        elif msg_lower == '1' or (etapa is None and interpretar_mensagem(msg) == 'agendamento'):
            if cliente:
                resposta = f"Vamos agendar seu horário, {cliente['nome']}! Com qual colaboradora você prefere se atender? Temos: {', '.join(COLABORADORAS)}."
                estados[numero] = {
                    "etapa": "colaboradora",
                    "nome": cliente["nome"]
                }
            else:
                resposta = "Vamos agendar seu horário! Qual o seu nome?"
                estados[numero]["etapa"] = "nome"

        elif etapa == "nome":
            estados[numero]["nome"] = msg.title()
            resposta = f"Ótimo, {estados[numero]['nome']}! Com qual de nossas profissionais você gostaria de se atender? Temos: {', '.join(COLABORADORAS)}."
            estados[numero]["etapa"] = "colaboradora"

        elif etapa == "colaboradora":
            nome = msg.title()
            if nome in COLABORADORAS or any(col.startswith(nome) for col in COLABORADORAS):
                # Encontra a colaboradora completa mesmo com nome parcial
                for col in COLABORADORAS:
                    if col.startswith(nome):
                        nome = col
                        break
                        
                estados[numero]["colaboradora"] = nome
                # Monta mensagem com categorias de serviços
                servicos_txt = ""
                for categoria, lista in SERVICOS.items():
                    servicos_txt += f"• {categoria.title()}: {', '.join(lista)}\n"
                
                resposta = f"Excelente escolha! A {nome} é especialista. Qual serviço você deseja?\n\n{servicos_txt}"
                estados[numero]["etapa"] = "servico"
            else:
                resposta = f"⚠️ Não encontrei essa profissional em nossa equipe. Por favor, escolha entre: {', '.join(COLABORADORAS)}."

        elif etapa == "servico":
            servico = msg.lower()
            estados[numero]["servico"] = servico
            
            # Verifica se a cliente está indecisa
            if "não sei" in servico or "indecisa" in servico:
                contexto = f"Cliente: {estados[numero]['nome']}, Colaboradora escolhida: {estados[numero]['colaboradora']}"
                sugestao = perguntar_gemini("Sugira serviços de salão personalizados para uma cliente indecisa, focando em cabelos e unhas.", contexto)
                resposta = f"💡 {sugestao}\n\nDiga-me qual serviço você escolheu para continuarmos o agendamento."
                estados[numero]["etapa"] = "servico"  # Mantém na mesma etapa
            else:
                # Verificar disponibilidade
                data_agenda = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                horarios_ocupados = carregar_horarios_ocupados(data_agenda)
                colaboradora = estados[numero]["colaboradora"]
                
                # Filtra horários disponíveis para a colaboradora escolhida
                horarios_livres = [h for h in HORARIOS_DISPONIVEIS if h not in horarios_ocupados.get(colaboradora, [])]
                
                if horarios_livres:
                    data_formatada = datetime.strptime(data_agenda, '%Y-%m-%d').strftime('%d/%m/%Y')
                    resposta = f"Para {servico} com {colaboradora} em {data_formatada}, temos estes horários disponíveis:\n\n"
                    resposta += ", ".join(horarios_livres)
                    resposta += "\n\nQual horário prefere?"
                    
                    estados[numero]["horarios_livres"] = horarios_livres
                    estados[numero]["data_agenda"] = data_agenda
                    estados[numero]["etapa"] = "horario"
                else:
                    # Tenta o próximo dia útil
                    data_agenda = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
                    horarios_ocupados = carregar_horarios_ocupados(data_agenda)
                    horarios_livres = [h for h in HORARIOS_DISPONIVEIS if h not in horarios_ocupados.get(colaboradora, [])]
                    
                    data_formatada = datetime.strptime(data_agenda, '%Y-%m-%d').strftime('%d/%m/%Y')
                    resposta = f"Para amanhã, a agenda da {colaboradora} está completa. Para {data_formatada}, temos:\n\n"
                    resposta += ", ".join(horarios_livres)
                    resposta += "\n\nEscolha um horário ou digite 'outro dia' para verificar outras datas."
                    
                    estados[numero]["horarios_livres"] = horarios_livres
                    estados[numero]["data_agenda"] = data_agenda
                    estados[numero]["etapa"] = "horario"

        elif etapa == "horario":
            escolha = msg.lower()
            
            if "outro dia" in escolha:
                # Avança mais um dia
                data_agenda = (datetime.strptime(estados[numero]["data_agenda"], '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
                horarios_ocupados = carregar_horarios_ocupados(data_agenda)
                colaboradora = estados[numero]["colaboradora"]
                horarios_livres = [h for h in HORARIOS_DISPONIVEIS if h not in horarios_ocupados.get(colaboradora, [])]
                
                data_formatada = datetime.strptime(data_agenda, '%Y-%m-%d').strftime('%d/%m/%Y')
                resposta = f"Para {data_formatada}, temos os seguintes horários:\n\n"
                resposta += ", ".join(horarios_livres)
                resposta += "\n\nQual horário prefere?"
                
                estados[numero]["horarios_livres"] = horarios_livres
                estados[numero]["data_agenda"] = data_agenda
                # Mantém a mesma etapa
            
            elif escolha in [h.lower() for h in estados[numero]["horarios_livres"]]:
                # Encontra o horário exato (preservando formato)
                for h in estados[numero]["horarios_livres"]:
                    if h.lower() == escolha:
                        horario = h
                        break
                
                # Salva o agendamento
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
                
                # Resposta personalizada baseada no serviço
                servico = dados["servico"].lower()
                if "unha" in servico or "manicure" in servico or "pedicure" in servico:
                    dica_adicional = "Lembre-se de vir com as unhas limpas, sem esmalte anterior para melhores resultados! 💅"
                elif "cabelo" in servico or "corte" in servico or "hidrat" in servico:
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
                    f"Aguardamos você, {dados['nome']}! Caso precise remarcar, é só enviar 'cancelar agendamento'. 💖"
                )
                
                estados[numero] = {"etapa": None}
            else:
                resposta = f"⚠️ Horário não disponível. Por favor, escolha entre: {', '.join(estados[numero]['horarios_livres'])}"

        # DICAS DE BELEZA
        elif msg_lower == '2' or (etapa is None and interpretar_mensagem(msg) == 'dica'):
            resposta = "✨ Adoraria te dar dicas personalizadas! Me conte o que você gostaria de saber sobre cabelos ou unhas. Por exemplo:\n\n- Como hidratar cabelos cacheados\n- Cuidados com unhas fracas\n- Produtos para cabelos tingidos"
            estados[numero]["etapa"] = "preferencia_dica"

        elif etapa == "preferencia_dica":
            dica = perguntar_gemini(msg, contexto_cliente)
            resposta = f"✨ {dica}\n\nPosso ajudar com mais alguma dica?"
            estados[numero]["etapa"] = None

        # FALAR COM ATENDENTE
        elif msg_lower == '3' or interpretar_mensagem(msg) == 'atendente':
            nome_cliente = cliente["nome"] if cliente else "a cliente"
            resposta = f"📞 Uma de nossas atendentes entrará em contato com você em breve, {nome_cliente}. Enquanto isso, posso responder suas dúvidas sobre nossos serviços!"

        # VER AGENDAMENTOS
        elif msg_lower == '4':
            agendamentos = recuperar_agendamentos(numero)
            if agendamentos:
                resposta = "🗓️ Seus próximos agendamentos:\n\n"
                for col, serv, hora, data in agendamentos:
                    data_formatada = datetime.strptime(data, '%Y-%m-%d').strftime('%d/%m/%Y')
                    resposta += f"• {data_formatada} às {hora} - {serv.title()} com {col}\n"
                resposta += "\nPara cancelar algum, digite '5'."
            else:
                resposta = "Você não possui agendamentos futuros. Que tal marcar um horário? Digite '1' para agendar!"

        # CANCELAR AGENDAMENTO
        elif msg_lower == '5' or interpretar_mensagem(msg) == 'cancelamento':
            agendamentos = recuperar_agendamentos(numero)
            if agendamentos:
                resposta = "Para cancelar um agendamento, entre em contato com nossa recepção pelo telefone (11) 9999-8888. Por medidas de segurança, preferimos fazer o cancelamento com atendimento pessoal. 🙏"
            else:
                resposta = "Você não possui agendamentos para cancelar. Deseja marcar um horário? Digite '1'."

        # PROCESSAMENTO NORMAL DE MENSAGENS
        elif etapa is None:
            # Tenta interpretar a mensagem como pergunta sobre beleza
            if any(palavra in msg_lower for palavra in ["cabelo", "unha", "hidrat", "corte", "tinta", "esmalte", "escova", "volume"]):
                # Usa o contexto do cliente para personalizar a resposta
                dica = perguntar_gemini(msg, contexto_cliente)
                resposta = f"✨ {dica}\n\nPosso ajudar com mais alguma coisa?"
            else:
                resposta = (
                    f"💖 Estou aqui para ajudar com dicas de beleza e agendamentos para cabelos e unhas! "
                    f"Digite 'menu' para ver todas as opções disponíveis."
                )

        # Envia e salva a mensagem
        if resposta:
            enviar_mensagem(id_sessao, numero, resposta)
            salvar_mensagem(numero, msg, resposta)

    # Tenta conectar
    try:
        sio.connect('http://localhost:3000')
        sio.wait()
    except Exception as e:
        print(f"[Erro] Falha ao conectar: {e}")
        # Tenta reconectar após alguns segundos
        time.sleep(5)
        ouvir_mensagens(id_sessao)

# ====== EXECUÇÃO ======
def main():
    criar_banco()
    print(f"[{datetime.now()}] 🌸 Iniciando Bella Beauty Bot 🌸")
    id_sessao = '8113'
    try:
        ouvir_mensagens(id_sessao)
    except KeyboardInterrupt:
        print("\n[✓] Bot encerrado pelo usuário")
    except Exception as e:
        print(f"[Erro Fatal] {e}")
        print("Tentando reiniciar em 10 segundos...")
        time.sleep(10)
        main()

if __name__ == "__main__":
    import time
    main()