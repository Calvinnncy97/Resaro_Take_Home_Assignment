import streamlit as st
import asyncio
import logging
import sys
from io import StringIO
from datetime import datetime
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.research_assistant import ResearchAssistant
from utils.logger import Logger


class StreamlitLogHandler(logging.Handler):
    """Custom log handler that captures logs for Streamlit display."""
    
    def __init__(self):
        super().__init__()
        self.log_records = []
        
    def emit(self, record):
        # Only capture logs from our custom Logger instances (agents.* and utils.* modules)
        if record.name.startswith('agents.') or record.name.startswith('utils.') or record.name.startswith('tools.'):
            log_entry = self.format(record)
            self.log_records.append({
                'timestamp': datetime.fromtimestamp(record.created),
                'level': record.levelname,
                'message': log_entry,
                'logger_name': record.name
            })
    
    def get_logs(self):
        return self.log_records
    
    def clear_logs(self):
        self.log_records = []


def setup_logging(log_level: str, log_handler: StreamlitLogHandler):
    """Setup logging with custom handler."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    log_handler.setFormatter(formatter)
    root_logger.addHandler(log_handler)


async def run_research_assistant(query: str, model_name: str):
    """Run the research assistant and return results."""
    assistant = ResearchAssistant(
        model_name=model_name,
        max_iterations=10
    )
    
    result = await assistant.research_and_generate_briefing(
        query=query,
    )
    
    return result


def main():
    st.set_page_config(
        page_title="Research Assistant Demo",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 Research Assistant Demo")
    st.markdown("Generate comprehensive company briefings using AI-powered research")
    
    if 'log_handler' not in st.session_state:
        st.session_state.log_handler = StreamlitLogHandler()
    
    if 'result' not in st.session_state:
        st.session_state.result = None
    
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        log_level = st.selectbox(
            "Log Level",
            options=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            index=1,
            help="Set the logging level for the application"
        )
        
        model_name = st.text_input(
            "Model Name",
            value="meta-llama/Llama-3.1-8B-Instruct",
            help="The LLM model to use for research"
        )
        
        show_logs = st.checkbox("Show Logs", value=False, help="Toggle to display execution logs")
        
        if st.button("Clear Logs", help="Clear all captured logs"):
            st.session_state.log_handler.clear_logs()
            st.rerun()
    
    setup_logging(log_level, st.session_state.log_handler)
    
    st.header("📝 Company Research Query")
    
    query = st.text_area(
        "Research Query",
        value="Research TechVentures Global, a technology company in the United States, San Francisco, operating in software and cloud services",
        help="Enter your research query about the company. Include the company name and any relevant context.",
        height=120
    )
    
    if st.button("🚀 Generate Briefing", type="primary", use_container_width=True):
        if not query or not query.strip():
            st.error("Please enter a research query")
        else:
            st.session_state.log_handler.clear_logs()
            
            with st.spinner("Researching company and generating briefing..."):
                try:
                    result = asyncio.run(run_research_assistant(
                        query=query,
                        model_name=model_name
                    ))
                    st.session_state.result = result
                    st.success("✅ Briefing generated successfully!")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    st.exception(e)
    
    if st.session_state.result:
        st.header("📊 Results")
        
        tabs = st.tabs(["📄 Final Briefing", "🔍 Research Steps", "🔒 Redaction Summary"])
        
        with tabs[0]:
            st.subheader(f"Company: {st.session_state.result.company_name}")
            st.text_area(
                "Briefing Content",
                value=st.session_state.result.briefing_content,
                height=500,
                disabled=True
            )
            
            st.download_button(
                label="📥 Download Briefing",
                data=st.session_state.result.briefing_content,
                file_name=f"{st.session_state.result.company_name.replace(' ', '_')}_briefing.txt",
                mime="text/plain"
            )
        
        with tabs[1]:
            st.subheader("Research Process")
            for i, step in enumerate(st.session_state.result.research_steps, 1):
                with st.expander(f"Step {i}", expanded=False):
                    st.write(step)
        
        with tabs[2]:
            st.subheader("Security Redaction Summary")
            st.json(st.session_state.result.redaction_summary)
    
    if show_logs:
        st.header("📋 Execution Logs")
        
        logs = st.session_state.log_handler.get_logs()
        
        if logs:
            log_container = st.container()
            with log_container:
                st.info(f"Total log entries: {len(logs)}")
                
                log_level_filter = st.multiselect(
                    "Filter by log level",
                    options=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                    default=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                )
                
                filtered_logs = [log for log in logs if log['level'] in log_level_filter]
                
                for log in filtered_logs:
                    level_color = {
                        'DEBUG': 'gray',
                        'INFO': 'blue',
                        'WARNING': 'orange',
                        'ERROR': 'red',
                        'CRITICAL': 'darkred'
                    }.get(log['level'], 'black')
                    
                    st.markdown(
                        f"<div style='padding: 5px; margin: 2px 0; border-left: 3px solid {level_color};'>"
                        f"<small><strong>[{log['level']}]</strong> {log['message']}</small>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                
                log_text = "\n".join([log['message'] for log in filtered_logs])
                st.download_button(
                    label="📥 Download Logs",
                    data=log_text,
                    file_name=f"research_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )
        else:
            st.info("No logs captured yet. Run a query to see logs.")
    
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray;'>"
        "Research Assistant Demo | Powered by LLM-based Agentic System"
        "</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
