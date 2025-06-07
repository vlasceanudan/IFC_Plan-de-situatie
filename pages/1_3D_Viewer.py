import streamlit as st
from streamlit.components.v1 import html
import base64

st.set_page_config(page_title="Vizualizare IFC 3D", layout="wide")

st.title("Vizualizare IFC 3D")

uploaded_file = st.file_uploader("Încărcați un fișier IFC", type=["ifc"], accept_multiple_files=False)

if uploaded_file is not None:
    b64_ifc = base64.b64encode(uploaded_file.getvalue()).decode()
    viewer_html = f"""
    <div id='viewer-container' style='width: 100%; height: 750px;'></div>
    <script type='module'>
      import {{ IfcViewerAPI }} from 'https://cdn.jsdelivr.net/npm/web-ifc-viewer@latest/dist/ifc-viewer-api.js';
      const container = document.getElementById('viewer-container');
      const viewer = new IfcViewerAPI({{ container }});
      viewer.grid.setGrid();
      viewer.axes.setAxes();
      const binaryString = atob('{b64_ifc}');
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {{
          bytes[i] = binaryString.charCodeAt(i);
      }}
      const url = URL.createObjectURL(new Blob([bytes]));
      await viewer.IFC.loadIfcUrl(url);
    </script>
    """
    html(viewer_html, height=750)
else:
    st.info("Încărcați un fișier IFC pentru a-l vizualiza în 3D.")
