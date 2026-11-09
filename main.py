from flask import Flask, jsonify, request, session, redirect, url_for, render_template_string
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import uuid
import requests

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'troque-por-chave-segura')

# Conexão MongoDB
client = MongoClient(os.getenv('MONGO_URI'))
db = client['video_site']
videos_collection = db['videos']
compras_collection = db['compras']

# ==========================================
# PÁGINA PRINCIPAL (SEM PRECISAR DE HTML SEPARADO)
# ==========================================
@app.route('/')
def index():
    videos = list(videos_collection.find({}, {'_id': 0}).sort('criado_em', -1))
    
    # Cole o seu HTML completo aqui dentro dessa string se quiser que rode direto do Python:
    html_direto = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="utf-8">
        <title>Meu Site Direto</title>
    </head>
    <body style="background:#000; color:#fff; font-family:sans-serif; text-align:center; padding-top:50px;">
        <h1>Rodando direto do Python sem arquivos HTML!</h1>
        <p>Total de itens no banco: {{ videos|length }}</p>
    </body>
    </html>
    """
    
    return render_template_string(html_direto, videos=videos)

# ==========================================
# VERIFICAR SE USUÁRIO JÁ COMPROU
# ==========================================
@app.route('/verificar-acesso/<video_id>')
def verificar_acesso(video_id):
    session_id = session.get('session_id', request.remote_addr)
    compra = compras_collection.find_one({
        'video_id': video_id,
        'session_id': session_id,
        'status': 'aprovado'
    })
    return jsonify({'liberado': bool(compra)})

# ==========================================
# INICIAR PAGAMENTO
# ==========================================
@app.route('/iniciar-pagamento', methods=['POST'])
def iniciar_pagamento():
    try:
        dados = request.json
        video_id = dados.get('video_id')
        
        video = videos_collection.find_one({'id': video_id})
        if not video:
            return jsonify({'erro': 'Vídeo não encontrado'}), 404
        
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
        
        mp_token = os.getenv('MP_TOKEN')
        headers = {
            'Authorization': f'Bearer {mp_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "description": f"Acesso: {video.get('titulo', 'Vídeo')}",
            "amount": 10.00,
            "payment_method_id": "pix",
            "notification_url": request.host_url.rstrip('/') + "/webhook-mercado-pago"
        }
        
        resp = requests.post(
            "https://api.mercadopago.com/v1/payments",
            headers=headers,
            json=payload
        )
        
        if resp.status_code != 201:
            return jsonify({'erro': 'Erro ao criar pagamento'}), 500
        
        pagamento = resp.json()
        pix_copia_cola = pagamento['point_of_interaction']['transaction_data']['qr_code']
        pagamento_id = pagamento['id']
        
        compras_collection.insert_one({
            'id': str(uuid.uuid4()),
            'video_id': video_id,
            'session_id': session_id,
            'pagamento_id': pagamento_id,
            'valor': 10.00,
            'status': 'pendente',
            'pix_copia_cola': pix_copia_cola,
            'criado_em': pagamento['date_created']
        })
        
        codigo_aleatorio = str(uuid.uuid4())[:8]
        
        return jsonify({
            'sucesso': True,
            'codigo_exibicao': codigo_aleatorio,
            'pagamento_id': pagamento_id
        })
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

# ==========================================
# DEVOLVER CÓDIGO PIX REAL NO CLICK DE COPIAR
# ==========================================
@app.route('/obter-pix-real/<pagamento_id>')
def obter_pix_real(pagamento_id):
    compra = compras_collection.find_one({'pagamento_id': int(pagamento_id)})
    if not compra:
        return jsonify({'erro': 'Não encontrado'}), 404
    return jsonify({'pix_copia_cola': compra.get('pix_copia_cola')})

# ==========================================
# WEBHOOK — Mercado Pago avisa quando pagar
# ==========================================
@app.route('/webhook-mercado-pago', methods=['POST'])
def webhook_mp():
    try:
        dados = request.json
        pagamento_id = dados.get('id')
        status = dados.get('status')
        
        if pagamento_id and status == 'approved':
            compras_collection.update_one(
                {'pagamento_id': pagamento_id},
                {'$set': {'status': 'aprovado'}}
            )
        return jsonify({'recebido': True})
    except:
        return jsonify({'ok': True})

# ==========================================
# HEALTH CHECK — pro UptimeRobot
# ==========================================
@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))
