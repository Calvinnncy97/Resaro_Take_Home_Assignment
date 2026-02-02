from agents.base_agent import OssBaseAgent
from typing import Optional
from pydantic import BaseModel
from utils.logger import Logger

logger = Logger(__name__)

PROMPT = """
You are a document translation assistant. Your task is to translate internal PDF documents from one language to another while preserving formatting, structure, and professional tone.

You will be given:
1. Target language - the language to translate to
2. Document content - the text content extracted from the PDF (mocked)

Your job is to:
- Translate the document content accurately from the source language to the target language
- Preserve the professional tone and formality level of the original document
- Maintain the structure and formatting intent (headings, paragraphs, lists)
- Keep technical terms, proper nouns, and company names consistent

Return your response as a JSON object with the following fields:
- translated_content: The full translated text
- sections_for_review: A list of section descriptions that may need human review
- translation_notes: Any important notes about the translation choices made

Target Language: {target_language}
Document Type: {document_type}

Document Content:
{document_content}
"""

class DocumentTranslationOutput(BaseModel):
    translated_content: str


class DocumentTranslator(OssBaseAgent):
    def __init__(self, model_name: str, api_key: Optional[str] = None):
        logger.info(f"Initializing DocumentTranslator with model: {model_name}")
        super().__init__(model_name, api_key)
    
    async def translate(
        self,
        document_content: str,
        source_language: str,
        target_language: str,
        document_type: str = "general"
    ) -> DocumentTranslationOutput:
        logger.info(f"Translating document from {source_language} to {target_language}")
        logger.debug(f"Document type: {document_type}")
        logger.debug(f"Content length: {len(document_content)} characters")
        
        full_prompt = PROMPT.format(
            target_language=target_language,
            document_content=document_content
        )
        logger.debug(f"Prompt length: {len(full_prompt)} characters")
        
        try:
            result = await self.generate(
                input=full_prompt,
                schema=DocumentTranslationOutput,
                think=True,
                temperature=0.3
            )
            
            logger.info(f"Translation completed successfully")
            
            return result
            
        except Exception as e:
            logger.error(f"Error during document translation: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    import asyncio
    import os
    
    async def main():
        log_level = os.getenv("LOG_LEVEL", "DEBUG")
        logger.logger.setLevel(logger._get_log_level(log_level))
        logger.info(f"Log level set to: {log_level}")
        
        translator = DocumentTranslator(
            model_name="meta-llama/Llama-3.1-8B-Instruct",
        )
        
        print("=" * 80)
        print("Example: Document Translation (Mocked PDF)")
        print("=" * 80)
        
        mock_document = """
CONFIDENTIAL BUSINESS AGREEMENT

This agreement is entered into on January 15, 2026, between:
- Party A: TechCorp International Ltd.
- Party B: Innovation Solutions Inc.

1. PURPOSE
The purpose of this agreement is to establish a partnership for the development
of artificial intelligence solutions in the healthcare sector.

2. TERMS AND CONDITIONS
2.1 Both parties agree to share resources and expertise.
2.2 All intellectual property developed jointly will be co-owned.
2.3 The agreement is valid for a period of 24 months.

3. CONFIDENTIALITY
All information shared under this agreement shall remain confidential and
shall not be disclosed to third parties without prior written consent.
"""
        
        print("Source Language: English")
        print("Target Language: Spanish")
        print("Document Type: contract")
        print()
        print("Original Content (excerpt):")
        print(mock_document[:200] + "...")
        print()
        
        result = await translator.translate(
            document_content=mock_document,
            source_language="English",
            target_language="Chinese",
            document_type="contract"    
        )
        
        print("=" * 80)
        print("Translation Result:")
        print("=" * 80)
        print(f"Confidence Score: {result.confidence_score:.2f}")
        print()
        print("Translated Content:")
        print(result.translated_content)
        print()
        
        if result.sections_for_review:
            print("Sections for Review:")
            for i, section in enumerate(result.sections_for_review, 1):
                print(f"  {i}. {section}")
            print()
        
        if result.translation_notes:
            print("Translation Notes:")
            print(result.translation_notes)
            print()
    
    asyncio.run(main())
