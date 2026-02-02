const API_URL = "http://localhost:8000/api/v1";

class API {
    static get token() {
        return localStorage.getItem("token");
    }

    static async request(endpoint, method = "GET", body = null) {
        const headers = {
            "Content-Type": "application/json"
        };
        if (this.token) {
            headers["Authorization"] = `Bearer ${this.token}`;
        }

        const config = {
            method,
            headers,
        };

        if (body) {
            config.body = JSON.stringify(body);
        }

        try {
            const res = await fetch(`${API_URL}${endpoint}`, config);

            // Handle 401 Unauthorized - token expired or invalid
            if (res.status === 401) {
                console.warn("Token expired or invalid. Redirecting to login...");
                localStorage.removeItem("token");
                localStorage.removeItem("role");
                // Redirect to login page
                window.location.href = "/static/login.html";
                throw new Error("Oturum süresi doldu. Lütfen tekrar giriş yapın.");
            }

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || "Something went wrong");
            }
            return data;
        } catch (err) {
            throw err;
        }
    }

    static post(endpoint, body) { return this.request(endpoint, "POST", body); }
    static get(endpoint) { return this.request(endpoint, "GET"); }
    static put(endpoint, body) { return this.request(endpoint, "PUT", body); }
    static delete(endpoint) { return this.request(endpoint, "DELETE"); }
}
