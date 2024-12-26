from flask import Flask, render_template, request, send_file
from datetime import datetime, timedelta
import calendar
import zipfile
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)

def calcular_dias_trabalho(data_admissao, escala):
    escalas = {
        "12x36": (1, 1),
        "5x2": "dias_uteis",
        "4x2": (4, 2),
        "5x1": (5, 1),
        "6x1": (6, 1),
    }

    if escala not in escalas:
        return []

    if 1 <= data_admissao.day <= 14:
        ano, mes = data_admissao.year, data_admissao.month
        ultimo_dia_mes = calendar.monthrange(ano, mes)[1]
        data_fim = datetime(ano, mes, ultimo_dia_mes)
    else:
        ano, mes = data_admissao.year, data_admissao.month
        proximo_mes = mes + 1 if mes < 12 else 1
        ano_proximo = ano if mes < 12 else ano + 1
        ultimo_dia_proximo_mes = calendar.monthrange(ano_proximo, proximo_mes)[1]
        data_fim = datetime(ano_proximo, proximo_mes, ultimo_dia_proximo_mes)

    if escala == "5x2":
        return obter_dias_uteis(data_admissao, data_fim)

    return obter_escala_trabalho(data_admissao, data_fim, escalas[escala])

def obter_dias_uteis(data_admissao, data_fim):
    dias_trabalho = []
    data_atual = data_admissao
    while data_atual <= data_fim:
        if data_atual.weekday() < 5:
            dias_trabalho.append(data_atual)
        data_atual += timedelta(days=1)
    return dias_trabalho

def obter_escala_trabalho(data_admissao, data_fim, escala):
    dias_trabalho, dias_folga = escala
    cronograma = []
    data_atual = data_admissao
    while data_atual <= data_fim:
        for _ in range(dias_trabalho):
            if data_atual > data_fim:
                break
            cronograma.append(data_atual)
            data_atual += timedelta(days=1)
        data_atual += timedelta(days=dias_folga)
    return cronograma

def calcular_total_vt(valor_vt, dias_trabalho):
    total_dias = len(dias_trabalho)
    return valor_vt * total_dias

def calcular_total_vr(dias_trabalho):
    total_dias = len(dias_trabalho)
    return 19.77 * total_dias

def parcela_vt(valor_vt, total_vt):
    quociente = int(float(total_vt) // (float(valor_vt) * 6))
    resto = total_vt % (float(valor_vt) * 6)
    
    parcelas_vt = [(float(valor_vt) * 6)] * quociente
    
    if resto > 0:
        parcelas_vt.append(resto)
    
    if len(parcelas_vt) > 1 and parcelas_vt[-1] < (float(valor_vt) * 6):
        parcelas_vt[-2] += parcelas_vt[-1]
        parcelas_vt.pop()
    
    return parcelas_vt

def parcela_vr(total_vr):
    quociente = int(float(total_vr) // (float(19.77) * 6))
    resto = total_vr % (float(19.77) * 6)
    
    parcelas_vr = [(float(19.77) * 6)] * quociente
    
    if resto > 0:
        parcelas_vr.append(resto)
    
    if len(parcelas_vr) > 1 and parcelas_vr[-1] < (float(19.77) * 6):
        parcelas_vr[-2] += parcelas_vr[-1]
        parcelas_vr.pop()
        
    return parcelas_vr

def gerar_pdf(dados, is_vr=False, parcelas=None):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    x = 40
    y = 750

    c.setFont("Helvetica-Bold", 16)
    titulo = f"{'VR' if is_vr else 'VT'} Inicial de {dados['nome']} - {dados['data_admissao']}"
    c.drawString(x, y, titulo)
    y -= 20

    c.setFont("Helvetica", 12)
    campos = [
        ("Nome Completo", dados["nome"]),
        ("Empresa", dados["empresa"]),
        ("Cliente", dados["cliente"]),
        ("Data de Admissão", dados["data_admissao"]),
        ("Escala de Trabalho", dados["escala"]),
        ("Função", dados["cargo"]),
        ("Horário", dados["turno"]),
        ("Banco", dados["banco"]),
        ("Tipo de chave Pix", dados["tipo_pix"]),
        ("Chave Pix", dados["chave_pix"]),
        ("Dias de Benefício", dados["dias_beneficio"]),
    ]

    for campo, valor in campos:
        c.drawString(x, y, f"{campo}: {valor}")
        y -= 20

    total = dados["total_vr"] if is_vr else dados["total_vt"]
    c.drawString(x, y, f"Valor Total do Benefício: R$ {round(total, 2)}")
    y -= 20
    parcelas = parcelas if is_vr else parcelas
    if parcelas:
        c.drawString(x, y, "Parcelas:")
        y -= 15
        for i, parcela in enumerate(parcelas, start=1):
            c.drawString(x, y, f"Parcela {i}: R$ {round(parcela, 2)}")
            y -= 15
            
    c.save()
    buffer.seek(0)
    return buffer

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            nome = request.form.get("nome")
            empresa = request.form.get("empresa")
            cliente = request.form.get("cliente")
            data_admissao_str = request.form.get("data_admissao")
            escala = request.form.get("escala")
            cargo = request.form.get("cargo")
            turno = request.form.get("turno")
            banco = request.form.get("banco")
            tipo_pix = request.form.get("tipo_pix")
            chave_pix = request.form.get("chave_pix")
            valor_vt = float(request.form.get("valor_vt"))

            data_admissao = datetime.strptime(data_admissao_str, "%Y-%m-%d")
            dias_trabalho = calcular_dias_trabalho(data_admissao, escala)

            dias_beneficio = len(dias_trabalho)
            total_vt = calcular_total_vt(valor_vt, dias_trabalho)
            parcelas_vt = parcela_vt(valor_vt, total_vt)
            total_vr = calcular_total_vr(dias_trabalho)
            parcelas_vr = parcela_vr(total_vr)

            dados = {
                "nome": nome,
                "empresa": empresa,
                "cliente": cliente,
                "data_admissao": data_admissao_str,
                "escala": escala,
                "cargo": cargo,
                "turno": turno,
                "banco": banco,
                "tipo_pix": tipo_pix,
                "chave_pix": chave_pix,
                "total_vt": total_vt,
                "total_vr": total_vr,
                "dias_beneficio": dias_beneficio,
            }

            pdf_buffer_vt = gerar_pdf(dados, parcelas=parcelas_vt)
            pdf_buffer_vr = gerar_pdf(dados, is_vr=True, parcelas=parcelas_vr)

            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr(f"{nome}_{data_admissao_str}_VT.pdf", pdf_buffer_vt.getvalue())
                zip_file.writestr(f"{nome}_{data_admissao_str}_VR.pdf", pdf_buffer_vr.getvalue())

            zip_buffer.seek(0)
            return send_file(
                zip_buffer,
                as_attachment=True,
                download_name=f"{nome}_{data_admissao_str}_relatorios.zip",
                mimetype="application/zip",
            )
        except ValueError:
            return render_template("documento.html", error="O valor de VT deve ser um número válido.")

    return render_template("documento.html")

if __name__ == "__main__":
    app.run(debug=True)
