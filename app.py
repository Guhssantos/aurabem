# -*- coding: utf-8 -*-
import streamlit as st
import google.generativeai as genai
import time
import re
import logging
import os # Import crucial para manipulação de caminhos

# --- Bloco de Configuração Inicial (com depuração de caminho MELHORADA) ---
# Configuração inicial do logger de depuração ANTES do logger principal
debug_logger = logging.getLogger("startup_debug")
stream_handler_debug = logging.StreamHandler()
formatter_debug = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
stream_handler_debug.setFormatter(formatter_debug)
if not debug_logger.handlers: # Evita adicionar handlers duplicados em reruns do Streamlit
    debug_logger.addHandler(stream_handler_debug)
debug_logger.setLevel(logging.DEBUG)

debug_logger.info(f"INÍCIO DA EXECUÇÃO DO SCRIPT.")

# Obtém o diretório onde o script app.py está localizado
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
debug_logger.info(f"Diretório do script (SCRIPT_DIR): {SCRIPT_DIR}")

# O nome do arquivo de prompt
SYSTEM_PROMPT_FILENAME = "system_prompt_aura.txt"

# Constrói o caminho absoluto para o arquivo de prompt
ABSOLUTE_PATH_TO_PROMPT_FILE = os.path.join(SCRIPT_DIR, SYSTEM_PROMPT_FILENAME)
debug_logger.info(f"Caminho absoluto construído para o arquivo de prompt: {ABSOLUTE_PATH_TO_PROMPT_FILE}")

current_working_directory = os.getcwd() # Ainda útil para referência
debug_logger.info(f"Diretório de trabalho atual (CWD - para referência): {current_working_directory}")
try:
    files_in_script_dir = os.listdir(SCRIPT_DIR)
    debug_logger.info(f"Arquivos e pastas no diretório do script ({SCRIPT_DIR}): {files_in_script_dir}")
except Exception as e_ls:
    debug_logger.error(f"Não foi possível listar arquivos no diretório do script ({SCRIPT_DIR}): {e_ls}")


# Configuração do Logging Principal do Aplicativo
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
st.title("💖 Aura Bem: Seu Companheiro Virtual")
st.caption("Um espaço seguro para conversar e encontrar acolhimento. Lembre-se, sou uma IA e não posso substituir um terapeuta profissional.")
st.divider()

# --- Bloco 3: Configuração da API Key e System Instruction ---
system_instruction_aura = ""

# Verificação explícita se o arquivo existe USANDO O CAMINHO ABSOLUTO
if not os.path.exists(ABSOLUTE_PATH_TO_PROMPT_FILE):
    debug_logger.error(f"VERIFICAÇÃO PRÉVIA: O arquivo '{SYSTEM_PROMPT_FILENAME}' NÃO FOI ENCONTRADO no caminho absoluto esperado: '{ABSOLUTE_PATH_TO_PROMPT_FILE}'.")
    debug_logger.error(f"Por favor, verifique se o arquivo '{SYSTEM_PROMPT_FILENAME}' existe EXATAMENTE com este nome e está na MESMA PASTA que o script Python ({SCRIPT_DIR}).")
    st.error(f"Erro Crítico de Configuração: O arquivo '{SYSTEM_PROMPT_FILENAME}' não foi encontrado em '{ABSOLUTE_PATH_TO_PROMPT_FILE}'. A Aura pode não funcionar como esperado. Verifique os logs do console para detalhes.")
    system_instruction_aura = "Você é um chatbot de apoio. Seja gentil e prestativo. Avise que não é um terapeuta."
    logger.warning(f"Usando instrução do sistema de fallback devido à ausência de '{SYSTEM_PROMPT_FILENAME}'.")
else:
    debug_logger.info(f"VERIFICAÇÃO PRÉVIA: O arquivo '{SYSTEM_PROMPT_FILENAME}' FOI ENCONTRADO no caminho absoluto: '{ABSOLUTE_PATH_TO_PROMPT_FILE}'.")
    try:
        with open(ABSOLUTE_PATH_TO_PROMPT_FILE, "r", encoding="utf-8") as f:
            system_instruction_aura = f.read()
        logger.info(f"Instrução do sistema '{SYSTEM_PROMPT_FILENAME}' carregada com sucesso de '{ABSOLUTE_PATH_TO_PROMPT_FILE}'.")
    except Exception as e:
        logger.error(f"Erro ao carregar instrução do sistema '{ABSOLUTE_PATH_TO_PROMPT_FILE}' MESMO APÓS VERIFICAÇÃO: {e}", exc_info=True)
        st.error(f"Erro ao carregar a personalidade da Aura: {e}")
        system_instruction_aura = "Falha ao carregar personalidade. Por favor, avise o desenvolvedor. Sou um chatbot de apoio, seja gentil."
        logger.warning(f"Usando instrução do sistema de fallback devido a erro de leitura de '{SYSTEM_PROMPT_FILENAME}'.")

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
    if not system_instruction_param or "fallback" in system_instruction_param.lower() or "personalidade" in system_instruction_param.lower() or "não é um terapeuta" in system_instruction_param.lower() :
        logger.warning(f"Inicializando modelo com uma instrução de sistema de fallback ou problemática: '{system_instruction_param[:100]}...'")
    else:
        logger.info(f"Inicializando modelo com system prompt personalizado de {len(system_instruction_param)} caracteres.")
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest",
            generation_config=generation_config,
            safety_settings=safety_settings,
            system_instruction=system_instruction_param
        )
        # logger.info(f"Modelo Generativo Gemini (gemini-1.5-flash-latest) inicializado.") # Log já feito acima
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
            
            if SESSION_CHAT_KEY not in st.session_state:
                initial_history_for_model = []
                for msg in st.session_state[SESSION_MESSAGES_KEY][:-1]:
                    role_for_gemini = "user" if msg["role"] == "user" else "model"
                    initial_history_for_model.append({"role": role_for_gemini, "parts": [msg["content"]]})
                
                st.session_state[SESSION_CHAT_KEY] = model.start_chat(history=initial_history_for_model)
                logger.info(f"Nova sessão de chat do Gemini iniciada com {len(initial_history_for_model)} mensagens de histórico.")

            with st.spinner("Aura está pensando... 💬"):
                response_stream = st.session_state[SESSION_CHAT_KEY].send_message(user_prompt, stream=True)

            last_chunk_for_safety_check = None # Para checar feedback no final
            for chunk in response_stream:
                last_chunk_for_safety_check = chunk # Guarda o último chunk
                if chunk.parts:
                    for part in chunk.parts:
                        full_response_stream += part.text
                        message_placeholder.markdown(full_response_stream + "▌")
                elif hasattr(chunk, 'text') and chunk.text: # Compatibilidade
                    full_response_stream += chunk.text
                    message_placeholder.markdown(full_response_stream + "▌")

                if chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                    logger.warning(f"Resposta parcialmente gerada e bloqueada por segurança: {chunk.prompt_feedback.block_reason}")
                    block_message_display = f"\n\n*(Sinto muito, não posso continuar essa resposta devido às diretrizes de segurança. Por favor, tente reformular sua mensagem ou abordar outro tópico.)*"
                    full_response_stream += block_message_display
                    message_placeholder.warning(full_response_stream.strip())
                    break
            
            bot_response_final = full_response_stream.strip()
            # Remove o cursor no final, mas somente se não foi bloqueado
            if not (last_chunk_for_safety_check and last_chunk_for_safety_check.prompt_feedback and last_chunk_for_safety_check.prompt_feedback.block_reason):
                message_placeholder.markdown(bot_response_final)


            # Checagem final de bloqueio se NENHUM texto foi gerado ou se o último chunk indicou bloqueio
            is_blocked = False
            block_reason_msg = "Não especificado"
            if last_chunk_for_safety_check and last_chunk_for_safety_check.prompt_feedback and last_chunk_for_safety_check.prompt_feedback.block_reason:
                is_blocked = True
                block_reason_msg = f"{last_chunk_for_safety_check.prompt_feedback.block_reason}"
                if hasattr(last_chunk_for_safety_check.prompt_feedback, 'block_reason_message'):
                    block_reason_msg += f" ({last_chunk_for_safety_check.prompt_feedback.block_reason_message})"
            
            if is_blocked and not bot_response_final.strip(): # Se bloqueado e sem texto algum
                logger.error(f"Prompt totalmente bloqueado pela API Gemini. Razão: {block_reason_msg}")
                bot_response_final = f"Sinto muito, sua mensagem não pôde ser processada devido às diretrizes de conteúdo ({block_reason_msg}). Tente reformular, por favor."
                message_placeholder.error(bot_response_final) # Sobrescreve o placeholder com erro
            elif not bot_response_final.strip() and not is_blocked: # Resposta genuinamente vazia
                logger.warning(f"Resposta vazia da IA para o prompt: '{user_prompt}'. Retornando fallback.")
                bot_response_final = "Sinto muito, não consegui pensar em uma resposta clara para isso no momento. Você poderia tentar reformular sua pergunta ou falar sobre outra coisa?"
                message_placeholder.markdown(bot_response_final) # Sobrescreve o placeholder


        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": bot_response_final})
        st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = False

    except genai.types.BlockedPromptException as bpe:
        logger.error(f"Prompt bloqueado pela API Gemini (BlockedPromptException): {bpe}", exc_info=True)
        error_msg_user = "Sua mensagem foi bloqueada por nossas diretrizes de segurança. Por favor, reformule sua pergunta."
        # st.error(error_msg_user) # Já é exibido no chat_message abaixo
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": error_msg_user})
        with st.chat_message("assistant"): st.error(error_msg_user)
    except Exception as e:
        error_msg_user = "Desculpe, ocorreu um problema técnico ao processar sua mensagem. Tente novamente mais tarde ou, se o problema persistir, avise o mantenedor do aplicativo."
        logger.error(f"Falha ao enviar mensagem para o Gemini ou processar resposta: {e}", exc_info=True)
        error_response_for_history = "Sinto muito, tive um problema técnico interno e não consegui responder. 😔"
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": error_response_for_history})
        with st.chat_message("assistant"): st.markdown(error_response_for_history)


# --- Bloco 11: Input e Lógica Principal ---
if prompt := st.chat_input("Digite sua mensagem aqui..."):
    logger.info(f"Usuário enviou: '{prompt[:50]}...' (tamanho: {len(prompt)})")

    contem_risco = any(regex.search(prompt) for regex in keywords_risco_regex)

    if contem_risco:
        logger.warning(f"Detectada palavra/expressão de RISCO na mensagem do usuário: '{prompt}'")
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            st.warning("**Importante: Se você está pensando em se machucar ou sente que está em perigo, por favor, busque ajuda profissional imediatamente.**")
            st.markdown(resposta_risco_padrao)
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": resposta_risco_padrao})
        st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = False
    else:
        send_message_to_aura(prompt)

# --- Bloco 12: Coleta de Feedback ---
if len(st.session_state[SESSION_MESSAGES_KEY]) > 1 and st.session_state[SESSION_MESSAGES_KEY][-1]["role"] == "assistant":
    last_aura_message = st.session_state[SESSION_MESSAGES_KEY][-1]["content"]
    is_risk_or_system_error_message = resposta_risco_padrao in last_aura_message or \
                               "problema técnico interno" in last_aura_message or \
                               "mensagem foi bloqueada" in last_aura_message or \
                               "não pôde ser processada" in last_aura_message or \
                               "Sinto muito, não consegui pensar em uma resposta clara" in last_aura_message # Não pedir feedback sobre fallback


    if not is_risk_or_system_error_message and not st.session_state.get(SESSION_FEEDBACK_SUBMITTED_KEY, False):
        st.divider()
        cols_feedback = st.columns([0.6, 0.2, 0.2], gap="small")
        with cols_feedback[0]:
            st.markdown("<div style='padding-top: 0.5em;'>Essa resposta foi útil?</div>", unsafe_allow_html=True)
        if cols_feedback[1].button("👍", key="feedback_positivo", help="Sim, foi útil!"):
            logger.info(f"Feedback: Positivo (👍) para: '{last_aura_message[:100]}...'")
            st.toast("Obrigado pelo seu feedback! 😊", icon="💖")
            st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = True
            st.rerun()
        if cols_feedback[2].button("👎", key="feedback_negativo", help="Não, não foi útil."):
            logger.info(f"Feedback: Negativo (👎) para: '{last_aura_message[:100]}...'")
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
        *   **Pausa e Respire:** Tire alguns minutos para respirar profundamente.
        *   **Movimente-se:** Uma caminhada leve ou alongamentos podem ajudar.
        *   **Conecte-se:** Converse com alguém de confiança.
        *(Lembre-se, estas são sugestões simples e não substituem o acompanhamento profissional.)*
        """)

# --- Bloco 14: Rodapé ---
st.divider()
st.caption(
    "Aura é uma Inteligência Artificial. Suas respostas são geradas por um modelo de linguagem. "
    "Ela **não é uma terapeuta** e não substitui o acompanhamento profissional. "
    "Em caso de emergência ou sofrimento intenso, **ligue para o CVV (188)** ou procure um profissional de saúde mental. "
)
debug_logger.info("FIM DA EXECUÇÃO DO SCRIPT.")
# --- Fim do app.py ---
