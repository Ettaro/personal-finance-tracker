# Financial Tracker (Computer Science Project)
Este é um projeto fullstack extremamente simples desenvolvido com **Django**, **HTML/CSS puro** e **SQLite**. O objetivo é demonstrar um sistema básico de controle financeiro de ponta a ponta.
**Live demo:** personal-finance-tracker-six-sable.vercel.app
## Funcionalidades
- **Dashboard**: Resumo de receitas, despesas e saldo total.
- **Transações**: Adicionar e listar transações (receitas ou despesas).
- **Categorias**: Criar e listar categorias para organizar as transações.

## Tecnologias Utilizadas
- **Backend**: Django (Python)
- **Frontend**: HTML5 e CSS3 (sem frameworks)
- **Banco de Dados**: SQLite (padrão do Django)

## Como Rodar o Projeto

### 1. Pré-requisitos
Certifique-se de ter o **Python 3** instalado em sua máquina.

### 2. Instalar o Django
Abra o terminal e execute:
```bash
pip install django
```

### 3. Preparar o Banco de Dados
Dentro da pasta raiz do projeto (onde está o arquivo `manage.py`), execute as migrações:
```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Iniciar o Servidor
Execute o comando:
```bash
python manage.py runserver
```

### 5. Acessar o Sistema
Abra o seu navegador e acesse:
[http://127.0.0.1:8000](http://127.0.0.1:8000)

---
*Projeto desenvolvido para fins educacionais.*
