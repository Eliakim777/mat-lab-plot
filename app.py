from flask import Flask, request, render_template_string, jsonify
import matplotlib
matplotlib.use('Agg') # Use the Agg backend for non-interactive plotting (important for server-side)
import matplotlib.pyplot as plt
import numpy as np
import io
import base64
import sys
import contextlib
import traceback # For better error reporting

app = Flask(__name__)

# Basic HTML template for the front-end
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Matplotlib Chart Generator</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f4; }
        .container { max-width: 900px; margin: auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #333; }
        textarea { width: 100%; height: 300px; margin-bottom: 15px; padding: 10px; border: 1px solid #ccc; border-radius: 4px; font-family: monospace; font-size: 14px; }
        button { padding: 12px 25px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button:hover { background-color: #0056b3; }
        #chartContainer { text-align: center; margin-top: 30px; }
        #chartImage { max-width: 100%; height: auto; border: 1px solid #ddd; box-shadow: 2px 2px 8px rgba(0,0,0,0.1); }
        #errorOutput { color: red; margin-top: 15px; white-space: pre-wrap; font-family: monospace; background-color: #ffe0e0; padding: 10px; border-radius: 4px; border: 1px solid red; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Generate Your Matplotlib Chart</h1>
        <p>Paste your Python Matplotlib code below. Make sure your code ends with <code>plt.show()</code> (it will be ignored but helps ensure a figure is generated) or simply generates a figure to be saved.</p>
        <textarea id="pythonCode">
import matplotlib.pyplot as plt
import numpy as np

# Data
outcomes = [
    "Reduced Loneliness", "Reduced Anger", "Reduced Bitterness",
    "Reduced Stagnation", "Sharing Faith", "Scripture Memorization",
    "Reduced Destructive Habits", "Reduced Pornography"
]
times_1_3 = [0, 0, 0, 0, 0, 0, 0, 0]
times_4_plus = [-30, -32, -40, -60, 228, 407, -57, -61]

# Set up the plot
x = np.arange(len(outcomes))
width = 0.35

fig, ax = plt.subplots(figsize=(12, 6))
bars1 = ax.bar(x - width/2, times_1_3, width, label="1-3 Times/Week", color="lightgray")
bars2 = ax.bar(x + width/2, times_4_plus, width, label="4+ Times/Week", color="skyblue")

# Customize
ax.set_xlabel("Outcomes")
ax.set_ylabel("Percentage Change in Likelihood (%)")
ax.set_title("Impact of Bible Reading Frequency on Emotional, Spiritual, and Behavioral Outcomes")
ax.set_xticks(x)
ax.set_xticklabels(outcomes, rotation=45, ha="right")
ax.legend()

# Add value labels on bars
for bar in bars2:
    height = bar.get_height()
    ax.text(
        bar.get_x() + bar.get_width()/2, height,
        f"{height}%", ha="center", va="bottom" if height >= 0 else "top"
    )

plt.tight_layout()
# Note: plt.show() is not needed here as the server captures the plot directly.
        </textarea>
        <button onclick="generateChart()">Generate Chart</button>

        <div id="errorOutput"></div>
        <div id="chartContainer">
            <img id="chartImage" src="" alt="Generated Matplotlib Chart" style="display:none;">
        </div>
    </div>

    <script>
        async function generateChart() {
            const pythonCode = document.getElementById('pythonCode').value;
            const chartImage = document.getElementById('chartImage');
            const errorOutput = document.getElementById('errorOutput');

            errorOutput.textContent = ''; // Clear previous errors
            chartImage.style.display = 'none'; // Hide previous image

            try {
                const response = await fetch('/generate-chart', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ code: pythonCode }),
                });

                const result = await response.json();

                if (response.ok) {
                    if (result.image) {
                        chartImage.src = 'data:image/png;base64,' + result.image;
                        chartImage.style.display = 'block';
                    } else if (result.message) {
                        // Handle cases where code ran but no image was generated
                        errorOutput.textContent = 'Warning: Code executed, but no chart was generated. ' + result.message;
                    }
                } else {
                    errorOutput.textContent = 'Error: ' + (result.error || 'Unknown error');
                }
            } catch (error) {
                console.error('Network or Fetch Error:', error);
                errorOutput.textContent = 'A network error occurred or server did not respond.';
            }
        }
    </script>
</body>
</html>
"""

# Custom context manager to capture stdout/stderr
@contextlib.contextmanager
def capture_output():
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    redirected_output = io.StringIO()
    sys.stdout = redirected_output
    sys.stderr = redirected_output
    try:
        yield redirected_output
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate-chart', methods=['POST'])
def generate_chart():
    user_code = request.json.get('code', '')

    # Create a dictionary to execute the code in
    # This helps isolate the execution but is NOT a security sandbox.
    exec_globals = {
        'plt': plt,
        'np': np,
        'io': io,
        'base64': base64,
        # Potentially add other safe modules if needed
    }
    exec_locals = {}

    buffer = io.BytesIO()
    chart_generated = False
    error_message = None
    output_message = ""

    # Capture print statements and errors
    with capture_output() as captured:
        try:
            # Execute the user's code
            # !!! WARNING: THIS IS A SECURITY RISK WITHOUT SANDBOXING !!!
            exec(user_code, exec_globals, exec_locals)

            # Check if any figures were created and save the current one
            if plt.get_fignums():
                fig = plt.gcf() # Get current figure
                fig.savefig(buffer, format='png')
                buffer.seek(0)
                chart_generated = True
            else:
                output_message = "No Matplotlib figure was created by your code."

        except Exception as e:
            error_message = traceback.format_exc() # Capture full traceback
        finally:
            plt.close('all') # Close all figures to prevent memory leaks

        output_message += captured.getvalue() # Add any captured print statements

    if error_message:
        return jsonify({'error': error_message}), 400
    elif chart_generated:
        graphic = base64.b64encode(buffer.getvalue()).decode('ascii')
        return jsonify({'image': graphic})
    else:
        return jsonify({'message': output_message})

if __name__ == '__main__':
    app.run(debug=True) # Turn off debug=True for production!