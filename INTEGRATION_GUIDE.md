# ReliefWeb Document Fetcher - Integration Guide

## Overview
This guide explains how to integrate the ReliefWeb Document Fetcher into your existing HTML application.

## Architecture

The system consists of two main parts:

1. **Backend (Python Flask)**: `reliefweb_server.py`
   - Handles API requests to ReliefWeb
   - Downloads PDFs in the background
   - Provides status updates and file downloads

2. **Frontend (HTML/CSS/JS)**: `reliefweb_component.html`
   - User interface for inputting disaster and country
   - Real-time progress tracking
   - Download management

## Setup Instructions

### Step 1: Install Backend Dependencies

```bash
pip install flask flask-cors requests
```

### Step 2: Start the Backend Server

```bash
python reliefweb_server.py
```

The server will start on `http://localhost:5000`

### Step 3: Integrate the Component into Your Existing HTML

You have **three integration options**:

---

## OPTION 1: Direct HTML Integration (Simplest)

Copy the entire content from `reliefweb_component.html` and paste it wherever you want the component to appear in your existing HTML file.

**Example:**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Application</title>
    
    <!-- Your existing styles -->
    <link rel="stylesheet" href="your-styles.css">
</head>
<body>
    <!-- Your existing header/navigation -->
    <header>
        <nav>...</nav>
    </header>

    <!-- Your existing content -->
    <main>
        <section>
            <!-- Your content here -->
        </section>

        <!-- ==================== RELIEFWEB COMPONENT ==================== -->
        <!-- Paste the entire reliefweb_component.html content here -->
        <style>
          /* ReliefWeb Fetcher Styles */
          .reliefweb-fetcher {
            /* ... all the CSS ... */
          }
          /* ... rest of the styles ... */
        </style>

        <div class="reliefweb-fetcher" id="reliefwebFetcher">
          <!-- ... all the HTML ... -->
        </div>

        <script>
          /* ... all the JavaScript ... */
        </script>
        <!-- ============================================================= -->
    </main>

    <!-- Your existing footer -->
    <footer>...</footer>

    <!-- Your existing scripts -->
    <script src="your-script.js"></script>
</body>
</html>
```

**Advantages:**
- ✅ Simplest integration
- ✅ No external file dependencies
- ✅ Everything self-contained

**Disadvantages:**
- ❌ Makes your HTML file larger
- ❌ Harder to update the component later

---

## OPTION 2: Separate Files with Import (Recommended)

Keep the component in separate files and link them in your HTML.

### Structure:
```
your-project/
├── index.html (your main file)
├── reliefweb/
│   ├── reliefweb.css
│   ├── reliefweb.js
│   └── reliefweb.html (just the HTML markup)
└── reliefweb_server.py
```

### Step-by-step:

**1. Split the component into three files:**

**reliefweb/reliefweb.css**
```css
/* Copy all the CSS from <style> tag */
.reliefweb-fetcher {
  --relief-primary: #2c5aa0;
  /* ... rest of the CSS ... */
}
```

**reliefweb/reliefweb.html**
```html
<!-- Copy just the HTML markup, no <style> or <script> tags -->
<div class="reliefweb-fetcher" id="reliefwebFetcher">
  <!-- ... all the HTML ... -->
</div>
```

**reliefweb/reliefweb.js**
```javascript
// Copy all the JavaScript from <script> tag
(function() {
  'use strict';
  // ... rest of the JavaScript ...
})();
```

**2. Include in your main HTML:**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Application</title>
    
    <!-- Your existing styles -->
    <link rel="stylesheet" href="your-styles.css">
    
    <!-- ReliefWeb component styles -->
    <link rel="stylesheet" href="reliefweb/reliefweb.css">
</head>
<body>
    <header>
        <nav>...</nav>
    </header>

    <main>
        <!-- Your content -->
        
        <!-- ReliefWeb component -->
        <div id="reliefwebContainer"></div>
    </main>

    <footer>...</footer>

    <!-- Your existing scripts -->
    <script src="your-script.js"></script>
    
    <!-- ReliefWeb component script -->
    <script src="reliefweb/reliefweb.js"></script>
    
    <!-- Load the HTML component -->
    <script>
      fetch('reliefweb/reliefweb.html')
        .then(response => response.text())
        .then(html => {
          document.getElementById('reliefwebContainer').innerHTML = html;
        });
    </script>
</body>
</html>
```

**Advantages:**
- ✅ Clean separation of concerns
- ✅ Easy to update the component
- ✅ Keeps main HTML file clean
- ✅ Reusable across multiple pages

**Disadvantages:**
- ❌ Requires a web server (won't work with file:// protocol due to CORS)

---

## OPTION 3: As a Web Component (Advanced)

Create a custom web component for maximum reusability.

**reliefweb/reliefweb-component.js**
```javascript
class ReliefWebFetcher extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    this.shadowRoot.innerHTML = `
      <style>
        /* Copy all CSS here */
        :host {
          display: block;
        }
        .reliefweb-fetcher {
          /* ... all styles ... */
        }
      </style>
      
      <!-- Copy all HTML here -->
      <div class="reliefweb-fetcher" id="reliefwebFetcher">
        <!-- ... all the HTML ... -->
      </div>
    `;
    
    // Initialize the component
    this.initializeComponent();
  }

  initializeComponent() {
    // Copy all the JavaScript initialization here
    const API_BASE_URL = 'http://localhost:5000/api';
    // ... rest of the JavaScript ...
  }
}

customElements.define('reliefweb-fetcher', ReliefWebFetcher);
```

**Usage in your HTML:**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>My Application</title>
    <link rel="stylesheet" href="your-styles.css">
</head>
<body>
    <header>...</header>
    
    <main>
        <!-- Simply use the custom element -->
        <reliefweb-fetcher></reliefweb-fetcher>
    </main>

    <footer>...</footer>

    <!-- Load the web component -->
    <script src="reliefweb/reliefweb-component.js"></script>
</body>
</html>
```

**Advantages:**
- ✅ True encapsulation (Shadow DOM prevents style conflicts)
- ✅ Extremely reusable
- ✅ Modern web standards
- ✅ Clean usage syntax

**Disadvantages:**
- ❌ More complex to implement
- ❌ Requires understanding of Web Components API

---

## CSS Class Naming Strategy

All CSS classes are prefixed with `reliefweb-` to prevent conflicts with your existing styles:

- `.reliefweb-fetcher` - Main container
- `.reliefweb-card` - Card component
- `.reliefweb-button` - Buttons
- `.reliefweb-input` - Input fields
- etc.

**If you have conflicts**, you can add additional nesting:

```css
#your-app-section .reliefweb-fetcher {
  /* Your overrides */
}
```

---

## Customizing the Component

### Change Colors

Modify the CSS variables in the `.reliefweb-fetcher` class:

```css
.reliefweb-fetcher {
  --relief-primary: #your-color;      /* Main brand color */
  --relief-secondary: #your-color;    /* Accent color */
  --relief-success: #your-color;      /* Success messages */
  --relief-error: #your-color;        /* Error messages */
  /* ... */
}
```

### Change API Endpoint

In the JavaScript section, update the `API_BASE_URL`:

```javascript
const API_BASE_URL = 'http://your-server.com:5000/api';
```

### Add More Countries

Edit the backend `reliefweb_server.py` in the `/api/countries` endpoint:

```python
countries = [
    {'code': 'HTI', 'name': 'Haiti'},
    {'code': 'YOUR', 'name': 'Your Country'},
    # Add more...
]
```

---

## Responsive Design

The component is fully responsive and will adapt to:
- Desktop (1200px+)
- Tablet (768px - 1199px)
- Mobile (<768px)

Test it by resizing your browser window!

---

## Testing the Integration

1. **Start the backend:**
   ```bash
   python reliefweb_server.py
   ```

2. **Open your HTML file** in a browser

3. **Test the workflow:**
   - Enter "Hurricane Melissa" as disaster name
   - Select "Haiti" from the dropdown
   - Click "Fetch Documents"
   - Watch the progress bar
   - Download the ZIP file when complete

---

## Troubleshooting

### "Failed to load countries"
- ✅ Make sure the Flask server is running
- ✅ Check the browser console for CORS errors
- ✅ Verify the API_BASE_URL is correct

### Folder selection not working
- ⚠️ Folder selection uses the File System API which has limited browser support
- ✅ Users can leave it blank to use the default folder
- ✅ The backend will create folders automatically

### Styles conflict with existing CSS
- ✅ Add more specific selectors
- ✅ Consider using Option 3 (Web Component) for true isolation
- ✅ Use CSS modules or scoped styles

### CORS errors
- ✅ Make sure `flask-cors` is installed
- ✅ Check that CORS is enabled in the backend
- ✅ If serving from a different domain, update CORS settings

---

## Production Deployment

When deploying to production:

1. **Update API URL** in JavaScript:
   ```javascript
   const API_BASE_URL = 'https://your-production-server.com/api';
   ```

2. **Use HTTPS** for both frontend and backend

3. **Configure CORS properly** in Flask:
   ```python
   from flask_cors import CORS
   CORS(app, origins=['https://your-frontend-domain.com'])
   ```

4. **Set up proper error handling** and logging

5. **Consider rate limiting** to prevent API abuse

---

## Next Steps: PDF Parsing

For parsing the downloaded PDFs, you can create another component that:
1. Lists all downloaded PDFs
2. Allows selection of PDFs to parse
3. Extracts text using libraries like PyPDF2, pdfplumber, or Apache Tika
4. Displays or exports the extracted text

Would you like me to create that component as well?

---

## Support

If you encounter any issues:
1. Check the browser console for JavaScript errors
2. Check the Flask server terminal for backend errors
3. Verify all dependencies are installed
4. Ensure the ReliefWeb API is accessible

## Summary

- **Option 1** (Direct HTML): Best for quick integration, single page
- **Option 2** (Separate Files): Best for maintainability, multiple pages
- **Option 3** (Web Component): Best for maximum reusability and isolation

Choose the option that best fits your project structure and requirements!
