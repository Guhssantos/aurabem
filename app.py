# -*- coding: utf-8 -*-
import streamlit as st
import google.generativeai as genai
import time
import re
import logging
import os

# --- Bloco de Configuração Inicial ---
# Logger de depuração inicial (opcional, mas útil durante o desenvolvimento)
debug_logger = logging.getLogger("startup_debug")
stream_handler_debug = logging.StreamHandler()
formatter_debug = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
stream_handler_debug.setFormatter(formatter_debug)
if not debug_logger.handlers: # Evita adicionar handlers duplicados em reruns do Streamlit
    debug_logger.addHandler(stream_handler_debug)
debug_logger.setLevel(logging.DEBUG)
debug_logger.info("Iniciando script app.py para Aura Bem...")


# Configuração do Logging Principal do Aplicativo
logging.basicConfig(
    level=logging.INFO, # Mude para logging.DEBUG para ver mais detalhes
    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# --- Constantes ---
SESSION_MESSAGES_KEY = "aura_bem_messages"
SESSION_CHAT_KEY = "aura_bem_chat_session"
SYSTEM_PROMPT_FILENAME = "system_prompt_aura_bem.txt" # Nome do arquivo de prompt
DEFAULT_SYSTEM_INSTRUCTION = (
    "Você é Aura Bem, uma IA de apoio. Seu objetivo é ouvir com empatia. "
    "Avise que você é uma IA e não uma psicóloga. "
    "Se o arquivo de personalidade completo não pôde ser carregado, peça desculpas."
)

# --- Bloco 1: Configuração da Página ---
st.set_page_config(
    page_title="Aura Bem - Sua Companheira de Bem-Estar",
    page_icon="💖",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- Bloco 2: Título e Descrição ---
st.title("💖 Aura Bem: Sua Companheira de Bem-Estar")
st.caption(
    "Um espaço seguro para conversar, encontrar acolhimento e explorar seus sentimentos. "
    "Lembre-se, sou Aura Bem, uma IA, e não substituo o aconselhamento de um psicólogo profissional."
)
st.divider()

# --- Bloco 3: Carregamento da System Instruction e Configuração da API ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ABSOLUTE_PATH_TO_PROMPT_FILE = os.path.join(SCRIPT_DIR, SYSTEM_PROMPT_FILENAME)
debug_logger.info(f"Tentando carregar prompt de: {ABSOLUTE_PATH_TO_PROMPT_FILE}")

system_instruction_aura_bem = ""
critical_error_loading_prompt = False

try:
    if os.path.exists(ABSOLUTE_PATH_TO_PROMPT_FILE):
        with open(ABSOLUTE_PATH_TO_PROMPT_FILE, "r", encoding="utf-8") as f:
            system_instruction_aura_bem = f.read()
        logger.info(f"Instrução do sistema '{SYSTEM_PROMPT_FILENAME}' carregada com sucesso.")
        if not system_instruction_aura_bem.strip():
            logger.warning(f"Arquivo '{SYSTEM_PROMPT_FILENAME}' está vazio. Usando fallback.")
            system_instruction_aura_bem = DEFAULT_SYSTEM_INSTRUCTION
            st.warning(f"Atenção: Arquivo de personalidade da Aura Bem ('{SYSTEM_PROMPT_FILENAME}') está vazio. Usando configuração padrão.")
    else:
        logger.error(f"ERRO CRÍTICO: Arquivo '{SYSTEM_PROMPT_FILENAME}' não encontrado em '{ABSOLUTE_PATH_TO_PROMPT_FILE}'.")
        debug_logger.error(f"Conteúdo do diretório '{SCRIPT_DIR}': {os.listdir(SCRIPT_DIR) if os.path.exists(SCRIPT_DIR) else 'Diretório não encontrado'}")
        st.error(
            f"Erro Crítico de Configuração: O arquivo de personalidade da Aura Bem ('{SYSTEM_PROMPT_FILENAME}') "
            f"não foi encontrado. A Aura Bem usará uma configuração básica. Verifique o deployment."
        )
        system_instruction_aura_bem = DEFAULT_SYSTEM_INSTRUCTION
        critical_error_loading_prompt = True
except Exception as e:
    logger.error(f"Erro ao ler '{ABSOLUTE_PATH_TO_PROMPT_FILE}': {e}", exc_info=True)
    st.error(f"Erro ao carregar personalidade da Aura Bem: {e}. Usando configuração básica.")
    system_instruction_aura_bem = DEFAULT_SYSTEM_INSTRUCTION
    critical_error_loading_prompt = True

# Configuração da API Key do Google
try:
    GOOGLE_API_KEY_APP = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY_APP)
    logger.info("Chave API do Google configurada com sucesso.")
except KeyError:
    logger.critical("Chave API do Google (GOOGLE_API_KEY) NÃO encontrada nos Secrets do Streamlit.")
    st.error("ERRO GRAVE: A Chave API do Google não foi configurada nos 'Secrets' do Streamlit. O aplicativo não pode se conectar à IA. Por favor, configure-a.")
    st.stop()
except Exception as e:
    logger.critical(f"Erro inesperado e grave ao configurar a API Key: {e}", exc_info=True)
    st.error(f"Erro grave ao configurar a API Key: {e}. O aplicativo não pode continuar.")
    st.stop()

# --- Bloco 4: Configuração do Modelo Gemini ---
generation_config = {
    "temperature": 0.65,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 1024,
}
safety_settings = [
    {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
    for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]
]

# --- Bloco 6: Definições de Segurança (CVV) e Detecção de Risco ---
keywords_risco_originais = [
    "me matar", "me mate", "suicidio", "suicídio", "não aguento mais viver", "quero morrer",
    "queria morrer", "quero sumir", "desistir de tudo", "acabar com tudo", "fazer mal a mim",
    "me cortar", "me machucar", "automutilação", "quero me jogar", "tirar minha vida",
    "sem esperança", "fim da linha"
]
keywords_risco_regex = [re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE) for kw in keywords_risco_originais]
resposta_risco_padrao = (
    "Sinto muito que você esteja passando por um momento tão difícil e pensando nisso. "
    "É muito importante buscar ajuda profissional **imediatamente**. Por favor, entre em contato com o "
    "**CVV (Centro de Valorização da Vida) ligando para o número 188**. A ligação é gratuita "
    "e eles estão disponíveis 24 horas por dia para conversar com você de forma sigilosa e segura. "
    "Você não está sozinho(a) e há pessoas prontas para te ouvir e ajudar. Por favor, ligue para eles agora. 🙏"
)

# --- Bloco 7: Função para Inicializar o Modelo ---
@st.cache_resource
def init_model(instruction: str):
    if instruction == DEFAULT_SYSTEM_INSTRUCTION:
        logger.warning("Inicializando modelo com instrução de sistema DE FALLBACK.")
    else:
        logger.info(f"Inicializando modelo com system prompt personalizado '{SYSTEM_PROMPT_FILENAME}'.")
    try:
        model_instance = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest",
            generation_config=generation_config,
            safety_settings=safety_settings,
            system_instruction=instruction
        )
        return model_instance
    except Exception as e_model:
        logger.critical(f"Erro GRAVE ao carregar o modelo de IA: {e_model}", exc_info=True)
        st.error(f"Erro grave ao carregar o modelo de IA: {e_model}. O app não pode continuar.")
        st.stop()

model = init_model(system_instruction_aura_bem)

# --- Bloco 8: Gerenciamento do Histórico da Conversa e Botão de Reset ---
if SESSION_MESSAGES_KEY in st.session_state and len(st.session_state[SESSION_MESSAGES_KEY]) > 1:
    if st.sidebar.button("🧹 Limpar Conversa Atual"):
        initial_message_reset = "Olá! Sou Aura Bem. Como posso te ajudar a se sentir um pouco melhor hoje? (Conversa reiniciada)"
        if critical_error_loading_prompt:
            initial_message_reset = (
                "Olá! Sou Aura Bem. Minha configuração de personalidade completa não carregou. "
                "Farei o meu melhor com uma configuração básica. (Conversa reiniciada)"
            )
        st.session_state[SESSION_MESSAGES_KEY] = [{"role": "assistant", "content": initial_message_reset}]
        if SESSION_CHAT_KEY in st.session_state: del st.session_state[SESSION_CHAT_KEY]
        logger.info("Histórico da conversa e sessão do Gemini reiniciados pelo usuário.")
        st.rerun()

if SESSION_MESSAGES_KEY not in st.session_state:
    initial_message_load = "Olá! Sou Aura Bem. Sinta-se à vontade para compartilhar como você está se sentindo. Estou aqui para ouvir. 😊"
    if critical_error_loading_prompt:
        initial_message_load = (
            "Olá! Sou Aura Bem. Parece que tive um problema ao carregar minha configuração completa de personalidade. "
            "Vou tentar te ajudar da melhor forma possível com uma configuração básica, mas peço desculpas se minha interação não for a ideal. "
            "Como você está se sentindo hoje?"
        )
    st.session_state[SESSION_MESSAGES_KEY] = [{"role": "assistant", "content": initial_message_load}]
    logger.info(f"Histórico de mensagens inicializado. Erro crítico no prompt: {critical_error_loading_prompt}")

# --- Bloco 9: Exibição do Histórico ---
for message in st.session_state[SESSION_MESSAGES_KEY]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Bloco 10: Função para Enviar Mensagem e Processar Resposta ---
def send_message_to_aura_bem(user_prompt: str):
    st.session_state[SESSION_MESSAGES_KEY].append({"role": "user", "content": user_prompt})
    with st.chat_message("user"): st.markdown(user_prompt)

    bot_response_final = ""
    try:
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response_stream = ""
            
            if SESSION_CHAT_KEY not in st.session_state:
                history_for_model = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]}
                                     for m in st.session_state[SESSION_MESSAGES_KEY][:-1]]
                st.session_state[SESSION_CHAT_KEY] = model.start_chat(history=history_for_model)
                logger.info(f"Nova sessão de chat Aura Bem iniciada com {len(history_for_model)} msgs de histórico.")

            with st.spinner("Aura Bem está refletindo... 🤔"):
                response_stream = st.session_state[SESSION_CHAT_KEY].send_message(user_prompt, stream=True)

            last_chunk = None
            for chunk in response_stream:
                last_chunk = chunk
                if chunk.parts:
                    for part in chunk.parts: full_response_stream += part.text
                elif hasattr(chunk, 'text') and chunk.text: full_response_stream += chunk.text
                message_placeholder.markdown(full_response_stream + "▌")

                if chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                    logger.warning(f"Resposta Aura Bem parcialmente gerada e bloqueada: {chunk.prompt_feedback.block_reason}")
                    full_response_stream += f"\n\n*(Minha resposta foi interrompida para manter nossa conversa segura. Poderia tentar de outra forma?)*"
                    message_placeholder.warning(full_response_stream.strip())
                    break
            
            bot_response_final = full_response_stream.strip()
            if not (last_chunk and last_chunk.prompt_feedback and last_chunk.prompt_feedback.block_reason):
                message_placeholder.markdown(bot_response_final)

            is_blocked_final = last_chunk and last_chunk.prompt_feedback and last_chunk.prompt_feedback.block_reason
            if is_blocked_final and not bot_response_final:
                reason = f"{last_chunk.prompt_feedback.block_reason}"
                logger.error(f"Prompt para Aura Bem totalmente bloqueado: {reason}")
                bot_response_final = f"Sua mensagem não pôde ser processada ({reason}). Vamos tentar de outra forma?"
                message_placeholder.error(bot_response_final)
            elif not bot_response_final and not is_blocked_final:
                logger.warning(f"Resposta vazia da Aura Bem para o prompt: '{user_prompt}'. Usando fallback.")
                bot_response_final = "Peço desculpas, parece que não encontrei as palavras certas para responder a isso. Poderia me dizer de outra forma ou explorar outro sentimento?"
                message_placeholder.markdown(bot_response_final)

        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": bot_response_final})

    except genai.types.BlockedPromptException as bpe:
        logger.error(f"BlockedPromptException (Aura Bem): {bpe}", exc_info=True)
        err_msg = "Sua mensagem foi bloqueada por diretrizes de segurança. Poderia tentar de uma forma diferente, por favor?"
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": err_msg})
        with st.chat_message("assistant"): st.error(err_msg)
    except Exception as e:
        logger.error(f"Falha ao enviar/processar mensagem (Aura Bem): {e}", exc_info=True)
        err_msg = "Desculpe, ocorreu um pequeno contratempo técnico da minha parte. Poderia tentar novamente, por favor? 😔"
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": err_msg})
        with st.chat_message("assistant"): st.markdown(err_msg)

# --- Bloco 11: Input e Lógica Principal ---
if prompt := st.chat_input("Como você está se sentindo hoje?..."):
    logger.info(f"Usuário (Aura Bem) enviou: '{prompt[:70]}...'")
    if any(regex.search(prompt) for regex in keywords_risco_regex):
        logger.warning(f"RISCO DETECTADO (Aura Bem) na mensagem: '{prompt}'")
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            st.warning("**Atenção:** Se você está pensando em se machucar ou sente que sua segurança está em risco, é muito importante buscar ajuda profissional imediatamente.")
            st.markdown(resposta_risco_padrao)
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": resposta_risco_padrao})
    else:
        send_message_to_aura_bem(prompt)

# Bloco 12 (Coleta de Feedback) foi REMOVIDO

# --- Bloco 13: Recursos Adicionais (Sidebar) ---
with st.sidebar:
    st.markdown("---")
    st.subheader("Apoio Adicional 🌻")
    with st.expander("Quando buscar ajuda profissional:", expanded=True):
        st.markdown(
            "Lembre-se, Aura Bem é uma IA para escuta e apoio, mas **não substitui um psicólogo.** "
            "Se você sente que precisa de um acompanhamento mais profundo, ou se o sofrimento emocional "
            "está impactando seu dia a dia, considere procurar um profissional de saúde mental. "
            "Eles podem oferecer o suporte especializado que você merece."
        )
    with st.expander("Contato de Emergência (Brasil):", expanded=True):
        st.markdown("- **CVV (Centro de Valorização da Vida):** Disque **188** (ligação gratuita, disponível 24h).")
        st.markdown("- **SAMU:** Disque **192** para emergências médicas.")
    with st.expander("Pequenas Práticas de Bem-Estar:", expanded=False):
        st.markdown(
            "*   **Respiração Consciente:** Inspire contando até 4, segure por 4, expire contando até 6. Repita algumas vezes.\n"
            "*   **Diário de Sentimentos:** Escrever sobre o que você sente pode ajudar a organizar os pensamentos.\n"
            "*   **Conexão Social:** Converse com um amigo ou familiar de confiança.\n"
            "*   **Movimento Gentil:** Uma caminhada leve ou alongamentos podem liberar tensões."
        )

# --- Bloco 14: Rodapé ---
st.divider()
st.caption(
    "Aura Bem é uma Inteligência Artificial desenvolvida para oferecer escuta e apoio emocional. "
    "Ela **NÃO é uma psicóloga** e suas sugestões não substituem o aconselhamento profissional qualificado. "
    "Em caso de emergência, ou se precisar de ajuda especializada, entre em contato com o **CVV (188)** ou procure um profissional de saúde mental."
)
debug_logger.info("Finalizando script app.py para Aura Bem.")
# --- Fim do app.py ---
