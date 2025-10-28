#!/usr/bin/env python3
"""
Script de verificação pré-deploy
Testa se a aplicação está pronta para produção
"""

import os
import sys
import subprocess
import importlib.util
from pathlib import Path

class DeployChecker:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.success = []
        
    def check_files(self):
        """Verifica se arquivos necessários existem"""
        required_files = [
            'app.py',
            'main.py', 
            'requirements.txt',
            'Dockerfile',
            'Procfile',
            '.streamlit/config.toml'
        ]
        
        print("🔍 Verificando arquivos necessários...")
        for file in required_files:
            if Path(file).exists():
                self.success.append(f"✅ {file}")
            else:
                self.errors.append(f"❌ {file} não encontrado")
                
    def check_requirements(self):
        """Verifica requirements.txt"""
        print("\n📦 Verificando dependências...")
        
        required_packages = [
            'streamlit',
            'langchain',
            'langchain-google-genai',
            'python-dotenv',
            'faiss-cpu'
        ]
        
        try:
            with open('requirements.txt', 'r') as f:
                content = f.read().lower()
                
            for package in required_packages:
                if package.lower() in content:
                    self.success.append(f"✅ {package}")
                else:
                    self.warnings.append(f"⚠️ {package} pode não estar incluído")
                    
        except FileNotFoundError:
            self.errors.append("❌ requirements.txt não encontrado")
            
    def check_environment(self):
        """Verifica configurações de ambiente"""
        print("\n🔑 Verificando configurações...")
        
        # Verificar se .env existe (para desenvolvimento)
        if Path('.env').exists():
            self.success.append("✅ .env encontrado (desenvolvimento)")
        else:
            self.warnings.append("⚠️ .env não encontrado (use secrets em produção)")
            
        # Verificar se API_KEY está configurada
        api_key = os.getenv('API_KEY')
        if api_key:
            self.success.append("✅ API_KEY configurada")
        else:
            self.warnings.append("⚠️ API_KEY não encontrada (configure nos secrets)")
            
    def check_imports(self):
        """Verifica se imports principais funcionam"""
        print("\n🐍 Verificando imports Python...")
        
        critical_imports = [
            'streamlit',
            'langchain',
            'dotenv',
            'pathlib'
        ]
        
        for module in critical_imports:
            try:
                __import__(module)
                self.success.append(f"✅ {module}")
            except ImportError:
                self.errors.append(f"❌ {module} não pode ser importado")
                
    def check_docs_folder(self):
        """Verifica pasta de documentos"""
        print("\n📄 Verificando documentos...")
        
        docs_path = Path('docs')
        if docs_path.exists():
            files = list(docs_path.glob('*'))
            if files:
                self.success.append(f"✅ {len(files)} arquivos em docs/")
            else:
                self.warnings.append("⚠️ Pasta docs/ vazia")
        else:
            self.warnings.append("⚠️ Pasta docs/ não encontrada")
            
    def check_gitignore(self):
        """Verifica .gitignore"""
        print("\n📝 Verificando .gitignore...")
        
        sensitive_patterns = ['.env', '__pycache__', '*.pyc', '.streamlit/secrets.toml']
        
        if Path('.gitignore').exists():
            with open('.gitignore', 'r') as f:
                gitignore_content = f.read()
                
            missing = []
            for pattern in sensitive_patterns:
                if pattern not in gitignore_content:
                    missing.append(pattern)
                    
            if missing:
                self.warnings.append(f"⚠️ .gitignore pode precisar: {', '.join(missing)}")
            else:
                self.success.append("✅ .gitignore configurado")
        else:
            self.warnings.append("⚠️ .gitignore não encontrado")
            
    def test_app_syntax(self):
        """Testa sintaxe do app.py"""
        print("\n🔧 Verificando sintaxe do app.py...")
        
        try:
            with open('app.py', 'r') as f:
                code = f.read()
            compile(code, 'app.py', 'exec')
            self.success.append("✅ app.py syntax OK")
        except SyntaxError as e:
            self.errors.append(f"❌ Erro de sintaxe em app.py: {e}")
        except FileNotFoundError:
            self.errors.append("❌ app.py não encontrado")
            
    def run_all_checks(self):
        """Executa todas as verificações"""
        print("🚀 VERIFICAÇÃO PRÉ-DEPLOY")
        print("=" * 50)
        
        self.check_files()
        self.check_requirements()
        self.check_environment()
        self.check_imports()
        self.check_docs_folder()
        self.check_gitignore()
        self.test_app_syntax()
        
        self.print_results()
        
    def print_results(self):
        """Imprime resultados finais"""
        print("\n" + "=" * 50)
        print("📊 RESULTADO DA VERIFICAÇÃO")
        print("=" * 50)
        
        if self.success:
            print("\n✅ SUCESSOS:")
            for item in self.success:
                print(f"   {item}")
                
        if self.warnings:
            print("\n⚠️ AVISOS:")
            for item in self.warnings:
                print(f"   {item}")
                
        if self.errors:
            print("\n❌ ERROS CRÍTICOS:")
            for item in self.errors:
                print(f"   {item}")
                
        print("\n" + "=" * 50)
        
        if self.errors:
            print("❌ DEPLOY NÃO RECOMENDADO - Corrija os erros primeiro")
            return False
        elif self.warnings:
            print("⚠️ DEPLOY POSSÍVEL - Revise os avisos")
            return True
        else:
            print("✅ PRONTO PARA DEPLOY!")
            return True

def main():
    """Função principal"""
    checker = DeployChecker()
    ready = checker.run_all_checks()
    
    if ready:
        print("\n🚀 PRÓXIMOS PASSOS:")
        print("1. git add .")
        print("2. git commit -m 'Deploy preparation'")
        print("3. git push origin main")
        print("4. Deploy no Streamlit Cloud: https://share.streamlit.io/")
        print("5. Configure API_KEY nos secrets")
    else:
        print("\n🔧 CORRIJA OS ERROS ANTES DO DEPLOY")
        
    return 0 if ready else 1

if __name__ == "__main__":
    sys.exit(main())