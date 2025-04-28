def menu_bella_bot():
    """Menu principal da BellaBot com experiência de conversa melhorada e organização clara"""
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
    boas_vindas = perguntar_gemini("Dê boas-vindas a um cliente novo do salão, apresente-se como assistente virtual Bella e mostre o menu de opções disponíveis de forma amigável.")
    print(f"\n{boas_vindas}")
    
    # Exibe menu de opções estruturado
    exibir_menu()
    
    # Loop principal de conversa
    while True:
        # Captura entrada do usuário
        entrada_usuario = input("\nVocê: ").strip()
        
        # Processamento das opções do menu
        if entrada_usuario.lower() in ['1', 'agendar', 'marcar', 'agendar horário', 'marcar horário']:
            print("\n✨ Iniciando processo de agendamento ✨")
            resposta = perguntar_gemini("O cliente escolheu agendar um horário. Confirme que vai iniciar o processo de agendamento e peça o nome completo.")
            print(resposta)
            conversa_agendamento()
            exibir_menu()
            continue
            
        elif entrada_usuario.lower() in ['2', 'dúvidas', 'duvidas', 'sugestoes', 'sugestões', 'informações', 'informacoes']:
            print("\n📋 Informações e Sugestões 📋")
            resposta = perguntar_gemini("O cliente deseja informações sobre serviços ou sugestões. Pergunte qual serviço específico gostaria de saber mais detalhes.")
            print(resposta)
            pergunta = input("Você: ").strip()
            prompt = f"O cliente está pedindo informações com a mensagem: '{pergunta}'. Forneça detalhes relevantes sobre os serviços e preços do salão de forma útil."
            resposta = perguntar_gemini(prompt, temperatura=0.6)
            print(resposta)
            exibir_menu()
            continue
            
        elif entrada_usuario.lower() in ['3', 'atendente', 'humano', 'pessoa', 'falar com atendente']:
            print("\n👩 Transferindo para Atendente Humana 👩")
            resposta = perguntar_gemini("O cliente deseja falar com uma atendente humana. Informe que vai transferir e peça um telefone para contato.")
            print(resposta)
            telefone = input("Você: ")
            resposta = perguntar_gemini(f"O cliente forneceu o contato: '{telefone}'. Confirme que uma atendente entrará em contato em breve e agradeça pela preferência.")
            print(resposta)
            exibir_menu()
            continue
            
        elif entrada_usuario.lower() in ['4', 'sair', 'exit', 'tchau', 'adeus', 'finalizar']:
            despedida = perguntar_gemini("O cliente deseja encerrar o atendimento. Responda com uma mensagem de despedida calorosa e convide para retornar.")
            print(despedida)
            print("\n✨ Atendimento finalizado. Obrigada por utilizar a BellaBot! ✨")
            break
            
        elif entrada_usuario.lower() == 'menu':
            exibir_menu()
            continue
            
        else:
            # Analisa a entrada para determinar intenção quando não é comando direto do menu
            intencao = entender_intencao(entrada_usuario)
            
            if intencao == "agendar":
                print("\n✨ Iniciando processo de agendamento ✨")
                resposta = perguntar_gemini(f"O cliente disse: '{entrada_usuario}' e quer fazer um agendamento. Confirme que vai iniciar o processo de agendamento e peça o nome completo.")
                print(resposta)
                conversa_agendamento()
            elif intencao == "informacao":
                prompt = f"O cliente está pedindo informações com a mensagem: '{entrada_usuario}'. Forneça detalhes relevantes sobre os serviços e preços do salão, de forma personalizada e útil."
                resposta = perguntar_gemini(prompt, temperatura=0.6)
                print(resposta)
            elif intencao == "atendente":
                resposta = perguntar_gemini(f"O cliente disse: '{entrada_usuario}' e parece querer falar com uma atendente humana. Informe que vai transferir para uma atendente e peça um telefone para contato.")
                print(resposta)
                telefone = input("Você: ")
                resposta = perguntar_gemini(f"O cliente forneceu o contato: '{telefone}'. Confirme que uma atendente entrará em contato em breve e agradeça pela preferência.")
                print(resposta)
            elif intencao == "sair":
                despedida = perguntar_gemini(f"O cliente disse: '{entrada_usuario}' e parece estar se despedindo. Responda com uma mensagem de despedida calorosa e convide para retornar.")
                print(despedida)
                print("\n✨ Atendimento finalizado. Obrigada por utilizar a BellaBot! ✨")
                break
            else:
                resposta = perguntar_gemini(f"O cliente disse: '{entrada_usuario}'. Responda de forma conversacional, amigável e útil. Ao final, lembre que pode digitar 'menu' para ver as opções.")
                print(resposta)
            
            # Exibe menu após qualquer interação não explícita do menu
            if intencao != "sair":
                print("\nDigite 'menu' para ver as opções disponíveis.")

def exibir_menu():
    """Exibe menu de opções formatado e organizado"""
    print("\n" + "="*50)
    print("🌟  MENU ESPAÇO DIVA - Como posso ajudar?  🌟")
    print("="*50)
    print("1️⃣  Agendar Horário")
    print("2️⃣  Dúvidas e Sugestões")
    print("3️⃣  Falar com Atendente")
    print("4️⃣  Sair")
    print("="*50)

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