## Task Tracker

Task Tracker is a Frappe app designed to track tasks and manage timesheets. It includes a desktop application that integrates with SowaanERP to create and manage timesheets.

### Installation

To install the required packages on the server, run the following commands:

```sh
sudo apt update
sudo apt install -y libgl1-mesa-glx
sudo apt install tesseract-ocr
```

### Getting the App

To get the app, clone the repository into your Frappe Bench apps directory:

```sh
cd ~/frappe-bench
bench get-app https://github.com/sowaan/task_tracker.git
bench setup requirements
bench build --app task_tracker
```

### Installing the App

To install the app on your Frappe site, run the following commands:

```sh
cd ~/frappe-bench
bench install-app task_tracker
bench --site your-site-name install-app task_tracker
bench restart
bench --site your-site-name migrate
```

Replace `your-site-name` with the name of your Frappe site.

### License

MIT
