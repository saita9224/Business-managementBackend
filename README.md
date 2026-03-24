# 🧾 Business Management Backend

A robust backend system for managing small and medium-sized businesses. This project provides a scalable API using **Django + Strawberry GraphQL**, with a custom-built **JWT authentication and Role-Based Access Control (RBAC)** system.

---

## 🚀 Tech Stack

* **Backend Framework:** Django
* **API Layer:** Strawberry GraphQL
* **Authentication:** Custom JWT + RBAC
* **Database:** SQLite (dev) / PostgreSQL (production)
* **Async Support:** ASGI + async resolvers

---

## 🔐 Authentication & Authorization

This project implements a **custom authentication system**.

### ✅ JWT Authentication

* Tokens are passed via:

```
Authorization: Bearer <token>
```

* Decoded using a custom service
* Integrated into GraphQL using a **Strawberry Schema Extension**

### ✅ Middleware Flow

* A custom `JWTMiddleware` runs on every GraphQL operation
* Extracts and validates JWT
* Attaches authenticated user to GraphQL context

```python
context.user = <Authenticated Employee | None>
```

---

## 🧠 Role-Based Access Control (RBAC)

The system uses a **fully custom RBAC design**:

### 👤 Employee (User)

* Custom user model (`AbstractBaseUser`)
* Identified by email
* Can have multiple roles

### 🏷 Roles

* Example: Admin, Manager, Cashier
* Assigned via `EmployeeRole`

### 🔑 Permissions

* Fine-grained access control (e.g. `create_order`, `view_expense`)
* Assigned to roles via `RolePermission`

### 🔗 Relationships

```
Employee → Role → Permission
```

---

## 🛡 Permission Enforcement

Permissions are enforced at the **resolver level** using decorators:

```python
@permission_required("create_order")
async def create_order(...)
```

### How it works:

1. Extract user from `info.context`
2. Check assigned roles
3. Validate required permission
4. Allow or raise error

Supports:

* Async resolvers
* Sync resolvers (via `sync_to_async`)

---

## ⚙️ Automatic Permission Registration

Permissions are dynamically loaded from each app:

```python
PERMISSIONS = {
    "create_order",
    "view_order",
}
```

### Loader behavior:

* Scans all installed apps
* Imports `permissions.py`
* Syncs permissions into database

---

## 📦 Features

### 🛒 Orders Management

* Order creation and tracking
* Group-based transactions

### 💸 Expense Tracking

* Supplier debt tracking
* Partial payments using `payment_group_id`

### 📊 Inventory Management

* Stock tracking
* Movement logs

### 👨‍💼 Employee Management

* Custom authentication system
* Role + permission assignment

---

## 🏗 Project Structure

```bash
backend/
│── middleware.py          # JWT Middleware (GraphQL)
│── manage.py
│
├── backend/
│   ├── settings.py
│   ├── schema.py          # Strawberry schema
│
├── employees/
│   ├── models.py          # Employee, Role, Permission
│   ├── decorators.py      # permission_required
│   ├── permissions_loader.py
│
├── apps/
│   ├── orders/
│   ├── expenses/
│   ├── inventory/
```

---

## 🔗 GraphQL API

Endpoint:

```
http://127.0.0.1:8000/graphql/
```

---

## 📌 Example Query

```graphql
query {
  orders {
    id
    name
    totalPrice
  }
}
```

---

## 🔄 Integration

Designed to integrate with:

* 📱 React Native frontend
* 🖥 PySide6 desktop app
* 💬 WhatsApp API (planned CRM interface)

---

## 🧠 Future Improvements

* JWT refresh tokens
* Permission caching (Redis)
* Audit logs for actions
* Multi-tenant architecture
* Real-time subscriptions

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Open a Pull Request

---

## 📄 License

MIT License

---
