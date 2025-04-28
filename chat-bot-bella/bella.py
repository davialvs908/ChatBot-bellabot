import requests
from datetime import datetime
import re
import os
from dotenv import load_dotenv
import json

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

colaboradoras = ["Ana", "Beatriz", "Carla"]
horarios_disponiveis = ["10:00", "11:00", "14:00", "16:00"]

# Variável global para armazenar o histórico da conversa
historico_conversa = []

# Sistema de extração de entidades
def extrair_entidades(texto, tipo_entidade):
    """
    Usa o Gemini para extrair entidades específicas de um texto
    tipo_entidade pode ser: 'horario', 'servico', 'colaboradora', etc.
    """
    try:
        prompt = f"""
        Analise o texto abaixo e extraia APENAS a entidade do tipo '{tipo_entidade}'. 
        Se não encontrar, responda com 'None'.
        
        Texto: "{texto}"
        
        Para extração de horário: identifique qualquer formato de hora (ex: '14', 'às 14', '14h', '14:00', 'duas da tarde', '14 horas', etc.)
        Para serviço: identifique serviços de beleza como 'corte', 'manicure', 'pedicure', 'hidratação', etc.
        Para colaboradora: identifique nomes de pessoas que pareçam ser profissionais
        
        Responda APENAS com a entidade extraída ou 'None', sem explicações adicionais.
        """
        
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generation_config": {"temperature": 0.1}  # Baixa temperatura para extração precisa
        }
        
        response = requests.post(URL, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            resposta_json = response.json()
            entity = resposta_json['candidates'][0]['content']['parts'][0]['text'].strip()
            return None if entity == 'None' else entity
        else:
            return None
    except Exception:
        return None

def horario_comercial():
    agora = datetime.now()
    hora = agora.hour
    return 8 <= hora <= 17

def perguntar_gemini(texto_usuario, historico=None, temperatura=0.7):
    """Função otimizada para consultar o Gemini com controle de temperatura"""
    global historico_conversa
    
    if historico is None:
        historico = historico_conversa
    
    try:
        # Instrução de sistema melhorada para comportamento mais humano
        sistema = """
        Você é Bella, uma assistente virtual de um salão de beleza chamado 'Espaço Diva'.
        
        OBJETIVOS:
        - Converse de forma natural e fluida como uma recepcionista real
        - Interprete as intenções do cliente mesmo quando não são explícitas
        - Seja prestativa, calorosa e use linguagem casual mas profissional
        - Faça sugestões personalizadas baseadas nas preferências mencionadas
        - Use poucos emojis (máximo 1-2 por mensagem) para manter um tom amigável
        - Mantenha respostas concisas (máximo 3 linhas) a menos que precise detalhar serviços
        
        CONHECIMENTO:
        - Você conhece todos os serviços do salão, preços e especialidades das colaboradoras
        - Ana é especialista em cortes modernos e coloração
        - Beatriz é especialista em tratamentos capilares e maquiagem
        - Carla é especialista em unhas e design de sobrancelhas
        
        PERSONALIDADE:
        - Entusiasmada sobre beleza e autoestima
        - Atenciosa com as necessidades dos clientes
        - Eficiente em resolver problemas
        - Positiva, mas não excessivamente animada
        
        IMPORTANTE: Suas respostas devem ser curtas, diretas e conversacionais.
        """
        
        # Contexto do salão mais detalhado
        contexto_salao = """
        O Espaço Diva oferece:
        - Cortes (R$60-120): corte simples, modelado, repicado, em camadas
        - Coloração (R$120-220): tintura simples, mechas, balayage, ombré hair
        - Tratamentos (R$80-150): hidratação, reconstrução, botox capilar, cauterização
        - Unhas (R$50-90): manicure, pedicure, unhas em gel, esmaltação em gel
        - Maquiagem (R$70-150): dia-a-dia, festas, noivas
        - Sobrancelhas (R$40-80): design, henna, micropigmentação
        - Massagens (R$100-180): relaxante, modeladora, drenagem linfática
        
        Horários disponíveis: 10h, 11h, 14h e 16h.
        """
        
        # Construindo o contexto da conversa com sistema melhorado
        contents = [
            {"role": "system", "parts": [{"text": sistema + contexto_salao}]}
        ]
        
        # Adiciona histórico de conversa, limitando para evitar token overflow
        for msg in historico[-10:] if len(historico) > 10 else historico:
            contents.append(msg)
        
        # Adiciona a mensagem atual do usuário
        contents.append({"role": "user", "parts": [{"text": texto_usuario}]})
        
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": contents,
            "generation_config": {
                "temperature": temperatura,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 250  # Limita o tamanho da resposta
            }
        }
        
        response = requests.post(URL, headers=headers, json=data, timeout=60)
        if response.status_code == 200:
            resposta_json = response.json()
            resposta = resposta_json['candidates'][0]['content']['parts'][0]['text']
            
            # Adiciona a interação ao histórico
            historico.append({"role": "user", "parts": [{"text": texto_usuario}]})
            historico.append({"role": "model", "parts": [{"text": resposta}]})
            
            # Atualiza o histórico global
            historico_conversa = historico
            
            return resposta
        else:
            return "Desculpe, estou com problemas técnicos no momento. Poderia tentar novamente?"
    except Exception as e:
        return f"Perdão pela interrupção. Estamos enfrentando instabilidade na conexão. Por favor, tente novamente."

def normalizar_horario(entrada_horario):
    """Função aprimorada para normalizar horários em diversos formatos"""
    if not entrada_horario:
        return None
        
    # Remove caracteres extras e converte para minúsculas
    entrada_limpa = entrada_horario.strip().lower()
    
    # Remove prefixos comuns
    entrada_limpa = re.sub(r'^(às|as|a|ao meio dia|ao 12|pela manhã|pela tarde|de tarde|de manhã|às\s+|as\s+)\s*', '', entrada_limpa)
    
    # Substitui variações comuns
    entrada_limpa = entrada_limpa.replace('hrs', '').replace('horas', '').replace('h', ':00')
    
    # Lidar com horas escritas por extenso (limitado)
    hora_extenso = {
        'dez': '10:00', 'onze': '11:00', 'duas': '14:00', 'quatro': '16:00',
        'meio dia': '12:00', 'meio-dia': '12:00'
    }
    for extenso, digital in hora_extenso.items():
        if extenso in entrada_limpa:
            entrada_limpa = digital
            break
    
    # Se for apenas um número, adiciona ":00"
    if re.match(r'^\d{1,2}$', entrada_limpa):
        entrada_limpa = f"{entrada_limpa}:00"
    
    # Formatação final para garantir padrão HH:MM
    padrao_hora = re.match(r'(\d{1,2})[:\.]?(\d{2})?', entrada_limpa)
    if padrao_hora:
        hora = int(padrao_hora.group(1))
        minutos = padrao_hora.group(2) or '00'
        # Se hora está em formato 24h, converte
        if 0 <= hora <= 23:
            return f"{hora:02d}:{minutos}"
    
    # Verifica se um horário aproximado foi encontrado nos disponíveis
    for horario in horarios_disponiveis:
        hora_apenas = horario.split(":")[0]
        if hora_apenas in entrada_limpa or f"{int(hora_apenas)}:00" in entrada_limpa:
            return horario
    
    return None

def verificar_horario_disponivel(horario):
    """Verifica se o horário normalizado está disponível"""
    horarios_ocupados = carregar_agendamentos()
    if horario in horarios_disponiveis and horario not in horarios_ocupados:
        return True
    return False

def salvar_agendamento(nome_cliente, numero_cliente, colaboradora, servico, horario):
    """Salva o agendamento em arquivo texto"""
    with open("agendamentos.txt", "a", encoding="utf-8") as arquivo:
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        arquivo.write(f"{agora} - Cliente: {nome_cliente} - Número: {numero_cliente} - {colaboradora} - {servico} às {horario}\n")

def carregar_agendamentos():
    """Carrega os horários já agendados"""
    horarios_ocupados = []
    if os.path.exists("agendamentos.txt"):
        with open("agendamentos.txt", "r", encoding="utf-8") as arquivo:
            for linha in arquivo:
                partes = linha.strip().split(" às ")
                if len(partes) > 1:
                    horario = partes[1].strip()
                    horarios_ocupados.append(horario)
    return horarios_ocupados

def obter_horarios_disponiveis():
    """Retorna lista de horários disponíveis"""
    horarios_ocupados = carregar_agendamentos()
    return [h for h in horarios_disponiveis if h not in horarios_ocupados]

def entender_intencao(texto):
    """Usa o Gemini para entender a intenção do usuário"""
    prompt = f"""
    Analise o texto do usuário abaixo e identifique a principal intenção.
    Responda APENAS com uma das seguintes opções:
    - agendar (se deseja marcar horário)
    - informacao (se está pedindo informações sobre serviços/preços)
    - atendente (se quer falar com uma pessoa real)
    - sair (se quer encerrar o atendimento)
    - outro (qualquer outra intenção)
    
    Texto do usuário: "{texto}"
    
    Resposta (apenas uma palavra):
    """
    
    try:
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generation_config": {"temperature": 0.1}
        }
        
        response = requests.post(URL, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            resposta_json = response.json()
            intencao = resposta_json['candidates'][0]['content']['parts'][0]['text'].strip().lower()
            return intencao
        else:
            return "outro"
    except Exception:
        return "outro"

def processar_entrada_usuario(texto_usuario, contexto=None):
    """
    Processa entrada do usuário para extrair entidades e entender intenções
    em um fluxo de conversa natural
    """
    if not contexto:
        contexto = {}
    
    # Entender intenção geral
    intencao = entender_intencao(texto_usuario)
    
    # Extrair entidades baseadas na intenção
    if intencao == "agendar":
        # Extrai possíveis entidades relacionadas a agendamento
        horario = extrair_entidades(texto_usuario, "horario")
        servico = extrair_entidades(texto_usuario, "servico")
        colaboradora = extrair_entidades(texto_usuario, "colaboradora")
        
        # Normaliza o horário se encontrado
        if horario:
            horario_norm = normalizar_horario(horario)
            if horario_norm:
                contexto["horario"] = horario_norm
        
        # Adiciona outras entidades ao contexto
        if servico:
            contexto["servico"] = servico
        if colaboradora:
            contexto["colaboradora"] = colaboradora
            
    return intencao, contexto

def conversa_agendamento():
    """Fluxo de conversa aprimorado para agendamentos"""
    contexto = {}
    
    # Mensagem inicial personalizada usando Gemini
    mensagem_boas_vindas = perguntar_gemini("Dê boas vindas a um cliente que acabou de entrar no salão e quer agendar um serviço. Seja breve e cordial.")
    print(f"\n{mensagem_boas_vindas}")
    
    # Coleta do nome, se não estiver no contexto
    if "nome" not in contexto:
        nome = input("Você: ").strip()
        if not nome:
            nome = "Cliente"
        
        # Tenta extrair intenção mesmo na primeira mensagem
        intencao, contexto = processar_entrada_usuario(nome, contexto)
        
        # Responde com base na primeira mensagem e pede o nome se não for saudação
        if len(nome) < 20:  # Provavelmente só um nome ou saudação
            resposta = perguntar_gemini(f"O cliente disse: '{nome}'. Responda cordialmente e pergunte o nome completo para o agendamento, caso não tenha sido informado.")
            print(resposta)
            nome = input("Você: ").strip()
            contexto["nome"] = nome
        else:
            # Se for uma mensagem mais longa, extraímos o nome e outras informações
            contexto["nome"] = extrair_entidades(nome, "nome") or "Cliente"
            resposta = perguntar_gemini(f"O cliente disse: '{nome}'. Extraímos o nome '{contexto['nome']}'. Responda de forma personalizada e pergunte o telefone para contato.")
            print(resposta)
    
    # Coleta do telefone
    if "telefone" not in contexto:
        telefone = input("Você: ").strip()
        intencao, contexto = processar_entrada_usuario(telefone, contexto)
        
        if re.search(r'\d', telefone):  # Verifica se contém números
            contexto["telefone"] = telefone
            
            # Se já temos informações suficientes no contexto, aproveitamos
            if "servico" in contexto and "colaboradora" in contexto and "horario" in contexto:
                prompt = f"O cliente {contexto['nome']} informou o telefone {contexto['telefone']}. Já identificamos que deseja {contexto['servico']} com {contexto['colaboradora']} às {contexto['horario']}. Confirme estes dados com o cliente de forma natural."
            else:
                prompt = f"O cliente {contexto['nome']} informou o telefone {contexto['telefone']}. Pergunte qual serviço deseja agendar hoje."
                
            resposta = perguntar_gemini(prompt)
            print(resposta)
        else:
            # Se não parece telefone, tentamos extrair outras informações úteis
            resposta = perguntar_gemini(f"O cliente disse: '{telefone}', que não parece ser um número de telefone. Peça educadamente que informe o telefone para contato.")
            print(resposta)
            telefone = input("Você: ").strip()
            contexto["telefone"] = telefone
            resposta = perguntar_gemini(f"Agradeça por informar o telefone {telefone} e pergunte qual serviço deseja agendar.")
            print(resposta)
    
    # Coleta do serviço desejado
    if "servico" not in contexto:
        servico = input("Você: ").strip()
        intencao, contexto = processar_entrada_usuario(servico, contexto)
        
        if "servico" not in contexto:
            # Tenta extrair o serviço da mensagem
            servico_extraido = extrair_entidades(servico, "servico")
            if servico_extraido:
                contexto["servico"] = servico_extraido
                resposta = perguntar_gemini(f"O cliente escolheu {servico_extraido}. Elogie a escolha e pergunte com qual profissional gostaria de agendar: Ana (cortes/cor), Beatriz (tratamentos/maquiagem) ou Carla (unhas/sobrancelhas).")
            else:
                # Se não conseguimos extrair, pedimos sugestões do Gemini
                resposta = perguntar_gemini(f"O cliente disse: '{servico}', mas não conseguimos identificar qual serviço deseja. Ofereça sugestões dos serviços do salão e pergunte qual deseja.")
            print(resposta)
            servico = input("Você: ").strip()
            contexto["servico"] = extrair_entidades(servico, "servico") or servico
    
    # Coleta da colaboradora
    if "colaboradora" not in contexto:
        prompt = f"Pergunte com qual profissional o cliente {contexto['nome']} gostaria de fazer {contexto['servico']}: Ana (cortes/cor), Beatriz (tratamentos/maquiagem) ou Carla (unhas/sobrancelhas)."
        resposta = perguntar_gemini(prompt)
        print(resposta)
        
        colaboradora_input = input("Você: ").strip()
        intencao, contexto = processar_entrada_usuario(colaboradora_input, contexto)
        
        if "colaboradora" not in contexto:
            # Tenta extrair a colaboradora da mensagem
            colaboradora_extraida = extrair_entidades(colaboradora_input, "colaboradora")
            if colaboradora_extraida and any(c.lower() in colaboradora_extraida.lower() for c in colaboradoras):
                # Encontra a correspondência exata da colaboradora
                for c in colaboradoras:
                    if c.lower() in colaboradora_extraida.lower():
                        contexto["colaboradora"] = c
                        break
            else:
                resposta = perguntar_gemini(f"O cliente disse: '{colaboradora_input}', mas não conseguimos identificar com qual profissional deseja agendar. Pergunte novamente, listando as opções: Ana, Beatriz ou Carla.")
                print(resposta)
                colaboradora_input = input("Você: ").strip()
                # Tenta uma correspondência simples
                for c in colaboradoras:
                    if c.lower() in colaboradora_input.lower():
                        contexto["colaboradora"] = c
                        break
                if "colaboradora" not in contexto:
                    contexto["colaboradora"] = "Ana"  # Default se não conseguir identificar
    
    # Coleta do horário
    if "horario" not in contexto:
        horarios_livres = obter_horarios_disponiveis()
        if not horarios_livres:
            resposta = perguntar_gemini("Informe que infelizmente todos os horários de hoje estão ocupados e pergunte se o cliente gostaria de agendar para amanhã.")
            print(resposta)
            return
        
        prompt = f"O cliente {contexto['nome']} escolheu {contexto['servico']} com {contexto['colaboradora']}. Pergunte qual horário prefere entre as opções disponíveis: {', '.join(horarios_livres)}."
        resposta = perguntar_gemini(prompt)
        print(resposta)
        
        horario_input = input("Você: ").strip()
        intencao, contexto = processar_entrada_usuario(horario_input, contexto)
        
        if "horario" not in contexto:
            # Tenta extrair o horário da mensagem
            horario_extraido = extrair_entidades(horario_input, "horario")
            if horario_extraido:
                horario_norm = normalizar_horario(horario_extraido)
                if horario_norm and verificar_horario_disponivel(horario_norm):
                    contexto["horario"] = horario_norm
                else:
                    resposta = perguntar_gemini(f"O cliente escolheu {horario_extraido}, mas esse horário não está disponível. Sugira os horários disponíveis: {', '.join(horarios_livres)}.")
                    print(resposta)
                    horario_input = input("Você: ").strip()
                    horario_extraido = extrair_entidades(horario_input, "horario")
                    if horario_extraido:
                        horario_norm = normalizar_horario(horario_extraido)
                        if horario_norm and verificar_horario_disponivel(horario_norm):
                            contexto["horario"] = horario_norm
            
            # Se ainda não temos horário, fazemos uma última tentativa
            if "horario" not in contexto:
                for h in horarios_livres:
                    if h.replace(':', '') in horario_input or h.split(':')[0] in horario_input:
                        contexto["horario"] = h
                        break
                
                # Se ainda não conseguimos, escolhemos o primeiro disponível
                if "horario" not in contexto and horarios_livres:
                    contexto["horario"] = horarios_livres[0]
    
    # Confirmação final e salvamento
    if "nome" in contexto and "telefone" in contexto and "servico" in contexto and "colaboradora" in contexto and "horario" in contexto:
        nome = contexto["nome"]
        telefone = contexto["telefone"]
        servico = contexto["servico"]
        colaboradora = contexto["colaboradora"]
        horario = contexto["horario"]
        
        prompt = f"""
        Confirmação de agendamento:
        - Cliente: {nome}
        - Telefone: {telefone}
        - Serviço: {servico}
        - Profissional: {colaboradora}
        - Horário: {horario}
        
        Confirme estes dados de forma conversacional e amigável, pergunte se está tudo certo para finalizar o agendamento.
        """
        
        confirmacao = perguntar_gemini(prompt)
        print(confirmacao)
        
        resposta_final = input("Você: ").strip().lower()
        if "sim" in resposta_final or "confirmo" in resposta_final or "ok" in resposta_final or "certo" in resposta_final:
            salvar_agendamento(nome, telefone, colaboradora, servico, horario)
            mensagem_sucesso = perguntar_gemini(f"O agendamento foi confirmado para {nome}, {servico} com {colaboradora} às {horario}. Agradeça e dê instruções para chegar com 10 minutos de antecedência.")
            print(mensagem_sucesso)
        else:
            mensagem_cancelamento = perguntar_gemini("O cliente não confirmou o agendamento. Responda educadamente, perguntando se deseja remarcar ou se houve algum problema.")
            print(mensagem_cancelamento)

def menu_bella_bot():
    """Menu principal da BellaBot com experiência de conversa aprimorada"""
    # Inicializa o histórico com informações do salão
    global historico_conversa
    
    contexto_salao = """
    O Espaço Diva é um salão de beleza completo com serviços de:
    - Cabelo: cortes, coloração, tratamentos
    - Unhas: manicure, pedicure, alongamento
    - Estética: maquiagem, design de sobrancelhas, massagens
    
    Temos três profissionais especializadas: Ana (cabelos), Beatriz (tratamentos) e Carla (unhas).
    Nossos horários disponíveis são: 10h, 11h, 14h e 16h.
    """
    
    # Reset do histórico para nova conversa
    historico_conversa = [
        {"role": "system", "parts": [{"text": f"Você é Bella, uma assistente virtual amigável do salão Espaço Diva. {contexto_salao}"}]}
    ]
    
    # Boas-vindas personalizada
    boas_vindas = perguntar_gemini("Dê boas-vindas a um cliente novo do salão, apresente-se brevemente como assistente virtual Bella e pergunte como pode ajudar hoje.")
    print(f"\n{boas_vindas}")
    
    # Loop principal de conversa
    while True:
        # Captura entrada do usuário
        entrada_usuario = input("\nVocê: ").strip()
        
        # Analisa a entrada para determinar intenção
        intencao = entender_intencao(entrada_usuario)
        
        # Se for intenção de sair, encerra o loop
        if intencao == "sair" or "tchau" in entrada_usuario.lower() or "adeus" in entrada_usuario.lower():
            despedida = perguntar_gemini(f"O cliente disse: '{entrada_usuario}' e parece estar se despedindo. Responda com uma mensagem de despedida calorosa e convide para retornar.")
            print(despedida)
            break
        
        # Se quer agendar, inicia o fluxo especializado
        elif intencao == "agendar":
            resposta = perguntar_gemini(f"O cliente disse: '{entrada_usuario}' e quer fazer um agendamento. Confirme que vai iniciar o processo de agendamento e peça o nome completo.")
            print(resposta)
            conversa_agendamento()
            continue
            
        # Se quer falar com atendente humana
        elif intencao == "atendente" or "atendente" in entrada_usuario.lower() or "pessoa real" in entrada_usuario.lower():
            resposta = perguntar_gemini(f"O cliente disse: '{entrada_usuario}' e parece querer falar com uma atendente humana. Informe que vai transferir para uma atendente e peça um telefone para contato.")
            print(resposta)
            telefone = input("Você: ")
            resposta = perguntar_gemini(f"O cliente forneceu o contato: '{telefone}'. Confirme que uma atendente entrará em contato em breve e agradeça pela preferência.")
            print(resposta)
            continue
            
        # Se pede informações sobre serviços
        elif intencao == "informacao" or "preço" in entrada_usuario.lower() or "valor" in entrada_usuario.lower():
            prompt = f"O cliente está pedindo informações com a mensagem: '{entrada_usuario}'. Forneça detalhes relevantes sobre os serviços e preços do salão, de forma personalizada e útil."
            resposta = perguntar_gemini(prompt, temperatura=0.6)
            print(resposta)
            continue
            
        # Para qualquer outra conversa, responde de forma natural
        else:
            resposta = perguntar_gemini(f"O cliente disse: '{entrada_usuario}'. Responda de forma conversacional, amigável e útil.")
            print(resposta)

# Função principal
if __name__ == "__main__":
    try:
        print("\n✨ Iniciando BellaBot - Assistente Virtual do Espaço Diva ✨")
        menu_bella_bot()
    except KeyboardInterrupt:
        print("\n\nAtendimento finalizado. Obrigada por utilizar a BellaBot!")
    except Exception as e:
        print(f"\nOcorreu um erro inesperado: {e}")
        print("Por favor, reinicie o sistema.")