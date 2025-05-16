# -*- coding: utf-8 -*-
import streamlit as st
import google.generativeai as genai
import time
import re
import logging
import os # Adicionado para depuração

# --- Bloco de Configuração Inicial (com depuração de caminho) ---
# Configuração inicial do logger de depuração ANTES do logger principal
# para garantir que estas mensagens apareçam.
# Este logger é temporário para diagnóstico.
debug_logger = logging.getLogger("startup_debug")
# Para garantir que as mensagens de debug apareçam no console imediatamente
stream_handler_debug = logging.StreamHandler()
formatter_debug = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
stream_handler_debug.setFormatter(formatter_debug)
debug_logger.addHandler(stream_handler_debug)
debug_logger.setLevel(logging.DEBUG) # Nível DEBUG para este logger específico

current_working_directory = os.getcwd()
debug_logger.info(f"INÍCIO DA EXECUÇÃO DO SCRIPT.")
debug_logger.info(f"Diretório de trabalho atual (CWD): {current_working_directory}")
try:
    files_in_cwd = os.listdir(current_working_directory)
    debug_logger.info(f"Arquivos e pastas no CWD ({current_working_directory}): {files_in_cwd}")
except Exception as e_ls:
    debug_logger.error(f"Não foi possível listar arquivos no CWD ({current_working_directory}): {e_ls}")

# Configuração do Logging Principal do Aplicativo (Melhorado e mais detalhado)
# Este logger será usado pelo restante do aplicativo.
logging.basicConfig(
    level=logging.INFO, # Pode ser alterado para DEBUG para ver mais detalhes da app
    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler()
        # logging.FileHandler("aura_app.log", encoding="utf-8") # Descomente para logar em arquivo
    ]
)
logger = logging.getLogger(__name__) # Logger principal para o restante do app

# --- Constantes para Session State ---
SESSION_MESSAGES_KEY = "aura_messages"
SESSION_CHAT_KEY = "aura_chat_session"
SESSION_FEEDBACK_SUBMITTED_KEY = "aura_feedback_submitted"

# --- Bloco 1: Configuração da Página ---
st.set_page_config(
    page_title="Aura - Chatbot de Apoio",
    page_icon="💖",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- Bloco 2: Título e Descrição ---
st.title("💖 Aura: Seu Companheiro Virtual")
st.caption("Um espaço seguro para conversar e encontrar acolhimento. Lembre-se, sou uma IA e não posso substituir um terapeuta profissional.")
st.divider()

# --- Bloco 3: Configuração da API Key e System Instruction ---
SYSTEM_PROMPT_FILE = "system_prompt_aura.txt"
system_instruction_aura = ""

# Verificação explícita se o arquivo existe ANTES de tentar abrir (para depuração)
# Usando o logger de depuração para estas mensagens
full_path_to_prompt_file = os.path.join(current_working_directory, SYSTEM_PROMPT_FILE)
if not os.path.exists(SYSTEM_PROMPT_FILE): # os.path.exists verifica relativo ao CWD por padrão
    debug_logger.error(f"VERIFICAÇÃO PRÉVIA: O arquivo '{SYSTEM_PROMPT_FILE}' NÃO FOI ENCONTRADO no diretório de trabalho atual: '{current_working_directory}'.")
    debug_logger.error(f"O sistema tentaria carregar de: '{full_path_to_prompt_file}' (se o nome do arquivo estivesse correto).")
    debug_logger.error(f"Por favor, verifique se o arquivo '{SYSTEM_PROMPT_FILE}' existe EXATAMENTE com este nome e está na MESMA PASTA que o script Python.")
    st.error(f"Erro Crítico de Configuração: O arquivo '{SYSTEM_PROMPT_FILE}' não foi encontrado. A Aura pode não funcionar como esperado. Verifique os logs do console para detalhes.")
    # Define um fallback mínimo para que o app não quebre totalmente, mas avise o usuário.
    system_instruction_aura = "Você é um chatbot de apoio. Seja gentil e prestativo. Avise que não é um terapeuta."
    logger.warning(f"Usando instrução do sistema de fallback devido à ausência de '{SYSTEM_PROMPT_FILE}'.")
else:
    debug_logger.info(f"VERIFICAÇÃO PRÉVIA: O arquivo '{SYSTEM_PROMPT_FILE}' FOI ENCONTRADO no diretório de trabalho atual: '{current_working_directory}'.")
    try:
        with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
            system_instruction_aura = f.read()
        logger.info(f"Instrução do sistema '{SYSTEM_PROMPT_FILE}' carregada com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao carregar instrução do sistema '{SYSTEM_PROMPT_FILE}' MESMO APÓS VERIFICAÇÃO: {e}", exc_info=True)
        st.error(f"Erro ao carregar a personalidade da Aura: {e}")
        system_instruction_aura = "Falha ao carregar personalidade. Por favor, avise o desenvolvedor. Sou um chatbot de apoio, seja gentil."
        logger.warning(f"Usando instrução do sistema de fallback devido a erro de leitura de '{SYSTEM_PROMPT_FILE}'.")

# Configuração da API Key do Google
try:
    GOOGLE_API_KEY_APP = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY_APP)
    logger.info("Chave API do Google configurada com sucesso via Streamlit Secrets.")
except KeyError:
    logger.error("Chave API do Google (GOOGLE_API_KEY) não encontrada nos Secrets do Streamlit.")
    st.error("Ops! Parece que a Chave API do Google não foi configurada nos 'Secrets' do Streamlit. Peça ajuda para configurá-la nas definições do app.")
    st.stop()
except Exception as e:
    logger.error(f"Erro inesperado ao configurar a API Key: {e}", exc_info=True)
    st.error(f"Erro inesperado ao configurar a API Key: {e}")
    st.stop()

# --- Bloco 4: Configuração do Modelo Gemini ---
generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 800,
}
safety_settings = [
    {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
    for c in [
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
    ]
]

# --- Bloco 6: Definições de Segurança (CVV) e Detecção de Risco Melhorada ---
keywords_risco_originais = [
    "me matar", "me mate", "suicidio", "suicídio",
    "não aguento mais viver", "quero morrer", "queria morrer",
    "quero sumir", "desistir de tudo", "acabar com tudo",
    "fazer mal a mim", "me cortar", "me machucar", "automutilação",
    "quero me jogar", "tirar minha vida", "sem esperança", "fim da linha"
]
keywords_risco_regex = [
    re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
    for keyword in keywords_risco_originais
]
logger.info(f"{len(keywords_risco_regex)} padrões de regex para detecção de risco compilados.")

resposta_risco_padrao = (
    "Sinto muito que você esteja passando por um momento tão difícil e pensando nisso. "
    "É muito importante buscar ajuda profissional **imediatamente**. Por favor, entre em contato com o "
    "**CVV (Centro de Valorização da Vida) ligando para o número 188**. A ligação é gratuita "
    "e eles estão disponíveis 24 horas por dia para conversar com você de forma sigilosa e segura. "
    "Você não está sozinho(a) e há pessoas prontas para te ouvir e ajudar. Por favor, ligue para eles agora."
)

# --- Bloco 7: Função para Inicializar o Modelo ---
@st.cache_resource
def init_model(system_instruction_param: str):
    # Verifica se a system_instruction_param não está vazia ou é apenas o fallback básico
    if not system_instruction_param or "fallback" in system_instruction_param.lower() or "personalidade" in system_instruction_param.lower():
        logger.warning(f"Inicializando modelo com uma instrução de sistema potencialmente problemática/fallback: '{system_instruction_param[:100]}...'")
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest",
            generation_config=generation_config,
            safety_settings=safety_settings,
            system_instruction=system_instruction_param
        )
        logger.info(f"Modelo Generativo Gemini (gemini-1.5-flash-latest) inicializado com system prompt de {len(system_instruction_param)} caracteres.")
        return model
    except Exception as e:
        logger.critical(f"Erro GRAVE ao carregar o modelo de IA: {e}", exc_info=True)
        st.error(f"Erro grave ao carregar o modelo de IA. O aplicativo não pode continuar. Detalhe: {e}")
        st.stop()

model = init_model(system_instruction_aura)

# --- Bloco 8: Gerenciamento do Histórico da Conversa e Botão de Reset ---
if SESSION_MESSAGES_KEY in st.session_state and len(st.session_state[SESSION_MESSAGES_KEY]) > 1:
    if st.sidebar.button("🧹 Limpar Conversa Atual"):
        st.session_state[SESSION_MESSAGES_KEY] = [{"role": "assistant", "content": "Olá! Sou Aura. Como você está se sentindo hoje? (Conversa reiniciada)"}]
        if SESSION_CHAT_KEY in st.session_state:
            del st.session_state[SESSION_CHAT_KEY]
        st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = False
        logger.info("Histórico da conversa e sessão do Gemini reiniciados pelo usuário.")
        st.rerun()

if SESSION_MESSAGES_KEY not in st.session_state:
    st.session_state[SESSION_MESSAGES_KEY] = [{"role": "assistant", "content": "Olá! Sou Aura. Como você está se sentindo hoje?"}]
    logger.info("Histórico de mensagens inicializado.")
    st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = False

# --- Bloco 9: Exibição do Histórico ---
for message in st.session_state[SESSION_MESSAGES_KEY]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Bloco 10: Função para Enviar Mensagem e Processar Resposta com Streaming ---
def send_message_to_aura(user_prompt: str):
    st.session_state[SESSION_MESSAGES_KEY].append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    bot_response_final = ""
    try:
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response_stream = ""
            
            # Prepara o histórico para o modelo Gemini
            # O Gemini espera 'parts' como uma lista de strings, e o role 'model' para o assistente
            # A API gerencia o histórico da sessão, mas podemos enviar o contexto atual explicitamente.
            # Para o send_message em uma sessão já iniciada, geralmente não precisamos reenviar todo o histórico,
            # mas para a primeira mensagem após a limpeza ou início, é crucial.
            # A lógica do SDK do Gemini para model.start_chat(history=...) e chat_session.send_message(...)
            # já lida com isso. Apenas garantimos que a sessão é iniciada corretamente.

            if SESSION_CHAT_KEY not in st.session_state:
                # Monta o histórico inicial para o `start_chat` se a sessão não existir
                # Pega todas as mensagens no `st.session_state[SESSION_MESSAGES_KEY]` exceto a última (que é o user_prompt atual)
                initial_history_for_model = []
                # Considera apenas as mensagens que já estão no histórico de Streamlit ANTES desta interação.
                # A mensagem do usuário atual (user_prompt) será enviada pelo send_message.
                # O system prompt já está configurado no modelo.
                # Aqui, o histórico que o Gemini precisa é o das interações passadas.
                for msg in st.session_state[SESSION_MESSAGES_KEY][:-1]: # Exclui o prompt atual do usuário
                    role_for_gemini = "user" if msg["role"] == "user" else "model"
                    initial_history_for_model.append({"role": role_for_gemini, "parts": [msg["content"]]})
                
                st.session_state[SESSION_CHAT_KEY] = model.start_chat(history=initial_history_for_model)
                logger.info(f"Nova sessão de chat do Gemini iniciada com {len(initial_history_for_model)} mensagens de histórico.")


            with st.spinner("Aura está pensando... 💬"):
                response_stream = st.session_state[SESSION_CHAT_KEY].send_message(user_prompt, stream=True)

            for chunk in response_stream:
                if chunk.parts:
                    for part in chunk.parts:
                        full_response_stream += part.text
                        message_placeholder.markdown(full_response_stream + "▌")
                elif hasattr(chunk, 'text') and chunk.text:
                    full_response_stream += chunk.text
                    message_placeholder.markdown(full_response_stream + "▌")

                if chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                    logger.warning(f"Resposta parcialmente gerada e bloqueada por segurança: {chunk.prompt_feedback.block_reason}")
                    block_message_display = f"\n\n*(Sinto muito, não posso continuar essa resposta devido às diretrizes de segurança. Por favor, tente reformular sua mensagem ou abordar outro tópico.)*"
                    full_response_stream += block_message_display
                    message_placeholder.warning(full_response_stream.strip()) # Usar warning para destacar
                    break

            if not full_response_stream.strip() and not (hasattr(response_stream, 'prompt_feedback') and response_stream.prompt_feedback and response_stream.prompt_feedback.block_reason):
                logger.warning(f"Resposta vazia da IA para o prompt: '{user_prompt}'. Retornando fallback.")
                bot_response_final = "Sinto muito, não consegui pensar em uma resposta clara para isso no momento. Você poderia tentar reformular sua pergunta ou falar sobre outra coisa?"
                message_placeholder.markdown(bot_response_final)
            else:
                bot_response_final = full_response_stream.strip()
                # Remove o cursor no final se a mensagem não foi bloqueada e cortada
                if not (chunk.prompt_feedback and chunk.prompt_feedback.block_reason):
                     message_placeholder.markdown(bot_response_final)


            if not bot_response_final and hasattr(response_stream, 'prompt_feedback') and response_stream.prompt_feedback.block_reason:
                block_reason = response_stream.prompt_feedback.block_reason
                block_message = getattr(response_stream.prompt_feedback, 'block_reason_message', "Motivo não especificado.")
                logger.error(f"Prompt bloqueado pela API Gemini. Razão: {block_reason}. Mensagem: {block_message}")
                bot_response_final = f"Sinto muito, sua mensagem não pôde ser processada devido às diretrizes de conteúdo ({block_reason}). Tente reformular, por favor."
                message_placeholder.error(bot_response_final)

        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": bot_response_final})
        st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = False

    except genai.types.BlockedPromptException as bpe:
        logger.error(f"Prompt bloqueado pela API Gemini (BlockedPromptException): {bpe}", exc_info=True)
        error_msg_user = "Sua mensagem foi bloqueada por nossas diretrizes de segurança. Por favor, reformule sua pergunta."
        st.error(error_msg_user) # Mostra o erro na UI
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": error_msg_user})
    except Exception as e:
        error_msg_user = "Desculpe, ocorreu um problema técnico ao processar sua mensagem. Tente novamente mais tarde ou, se o problema persistir, avise o mantenedor do aplicativo."
        logger.error(f"Falha ao enviar mensagem para o Gemini ou processar resposta: {e}", exc_info=True)
        # Não precisa do st.error(error_msg_user) aqui se o placeholder já sumiu
        # A mensagem de erro já será adicionada ao chat.
        error_response_for_history = "Sinto muito, tive um problema técnico interno e não consegui responder. 😔"
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": error_response_for_history})
        with st.chat_message("assistant"): # Garante que a mensagem de erro apareça no chat
            st.markdown(error_response_for_history)

# --- Bloco 11: Input e Lógica Principal ---
if prompt := st.chat_input("Digite sua mensagem aqui..."):
    logger.info(f"Usuário enviou: '{prompt[:50]}...' (tamanho: {len(prompt)})")

    contem_risco = any(regex.search(prompt) for regex in keywords_risco_regex)

    if contem_risco:
        logger.warning(f"Detectada palavra/expressão de RISCO na mensagem do usuário: '{prompt}'")
        # Adiciona mensagem do usuário ao histórico ANTES da resposta de risco
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "user", "content": prompt})
        with st.chat_message("user"): # Exibe a mensagem do usuário
            st.markdown(prompt)

        with st.chat_message("assistant"): # Exibe a resposta de risco
            st.warning("**Importante: Se você está pensando em se machucar ou sente que está em perigo, por favor, busque ajuda profissional imediatamente.**")
            st.markdown(resposta_risco_padrao)
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": resposta_risco_padrao})
        st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = False
    else:
        send_message_to_aura(prompt)

# --- Bloco 12: Coleta de Feedback ---
if len(st.session_state[SESSION_MESSAGES_KEY]) > 1 and st.session_state[SESSION_MESSAGES_KEY][-1]["role"] == "assistant":
    # Garante que a última mensagem não seja a de risco ou erro para pedir feedback sobre ela.
    last_aura_message = st.session_state[SESSION_MESSAGES_KEY][-1]["content"]
    is_risk_or_error_message = resposta_risco_padrao in last_aura_message or \
                               "problema técnico interno" in last_aura_message or \
                               "mensagem foi bloqueada" in last_aura_message or \
                               "não pôde ser processada" in last_aura_message


    if not is_risk_or_error_message and not st.session_state.get(SESSION_FEEDBACK_SUBMITTED_KEY, False):
        st.divider()
        cols_feedback = st.columns([0.6, 0.2, 0.2], gap="small") # Ajuste para melhor alinhamento
        with cols_feedback[0]:
            st.markdown("<div style='padding-top: 0.5em;'>Essa resposta foi útil?</div>", unsafe_allow_html=True)
        if cols_feedback[1].button("👍", key="feedback_positivo", help="Sim, foi útil!"):
            logger.info(f"Feedback da conversa: Positivo (👍) para a resposta: '{last_aura_message[:100]}...'")
            st.toast("Obrigado pelo seu feedback! 😊", icon="💖")
            st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = True
            st.rerun()
        if cols_feedback[2].button("👎", key="feedback_negativo", help="Não, não foi útil."):
            logger.info(f"Feedback da conversa: Negativo (👎) para a resposta: '{last_aura_message[:100]}...'")
            st.toast("Obrigado pelo seu feedback. Vamos continuar melhorando! 🙏", icon="💡")
            st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = True
            st.rerun()

# --- Bloco 13: Recursos Adicionais ---
with st.sidebar:
    st.markdown("---")
    st.subheader("Recursos Úteis 💡")
    with st.expander("Para momentos de crise ou necessidade de apoio:", expanded=False):
        st.markdown("- **CVV (Centro de Valorização da Vida):** Disque **188** (ligação gratuita, 24h).")
        st.markdown("- **SUS:** Procure um CAPS (Centro de Atenção Psicossocial) perto de você.")
        st.markdown("- Lembre-se: Você não está sozinho(a). Buscar ajuda é um ato de coragem.")

    with st.expander("Dicas rápidas de bem-estar:", expanded=False):
        st.markdown("""
        *   **Pausa e Respire:** Tire alguns minutos para respirar profundamente. Inspire pelo nariz contando até 4, segure por 4 e expire pela boca contando até 6.
        *   **Movimente-se:** Uma caminhada leve ou alguns alongamentos podem ajudar a aliviar a tensão.
        *   **Conecte-se:** Converse com um amigo, familiar ou alguém de confiança.
        *   **Pequenos Prazeres:** Ouça uma música que você gosta, assista a algo leve, leia um trecho de um livro.
        *(Lembre-se, estas são sugestões simples e não substituem o acompanhamento profissional.)*
        """)

# --- Bloco 14: Rodapé ---
st.divider()
st.caption(
    "Aura é uma Inteligência Artificial e suas respostas são geradas por um modelo de linguagem. "
    "Ela **não é uma terapeuta** e não substitui o acompanhamento psicológico ou psiquiátrico profissional. "
    "Em caso de emergência, sofrimento intenso ou necessidade de apoio especializado, **ligue para o CVV (188)** ou procure um profissional de saúde mental. "
    "Sua privacidade é importante. As conversas podem ser registradas anonimamente para fins de melhoria do sistema."
)
debug_logger.info("FIM DA EXECUÇÃO DO SCRIPT.")
# --- Fim do app.py ---
