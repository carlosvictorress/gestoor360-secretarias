# extensions.py
# Este arquivo vai guardar as extensões do Flask para evitar importações circulares.

from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

# Apenas criamos as variáveis aqui, sem conectar ao 'app'
db = SQLAlchemy()
bcrypt = Bcrypt()
