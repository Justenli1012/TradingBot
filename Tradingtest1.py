import tkinter as tk 
from tkinter import ttk, messagebox
import json
import time
import threading
import random
import alpaca_trade_api as tradeapi
from groq import Groq #Can be any LLM

#Find the following API keys from your Alpaca account dashboard, and Groq (or other LLM) insert them here
LLM_API_KEY = ""
LLAMA_API_KEY = ""
LLAMA_API_SECRET_KEY = ""

client = Groq(api_key=LLM_API_KEY)
key = LLAMA_API_KEY
secret_key = LLAMA_API_SECRET_KEY

DATA_FILE = "equities.json"

BASE_URL = "https://paper-api.alpaca.markets/"
api = tradeapi.REST(key, secret_key, BASE_URL, api_version="v2")

def fetch_portfolio():
    positions = api.list_positions()
    portfolio = []
    for pos in positions:
        portfolio.append({
            'symbol': pos.symbol,
            'qty': pos.qty,
            'entry_price': pos.avg_entry_price,
            'current_price': pos.current_price,
            'unrealized_pl': pos.unrealized_pl,
            'side': 'long' 
        })
    return portfolio

def fetch_open_orders():
    orders = api.list_orders(status='open')
    open_orders = []
    for order in orders:
        open_orders.append({
            'symbol': order.symbol,
            'qty': order.qty,
            'limit_price': order.limit_price,
            'side': 'buy' 
        })

def LLM_response(message):
    portfolio_data = fetch_portfolio()
    open_orders = fetch_open_orders()

    pre_prompt = f"""
    You are an AI Portfolio Mananger responsible for anaylzing my portfolio
    Your tasks are the following:
    1.) Evaluate risk exposures of my current holdings
    2.) Analyze my open limit orders and their potential impact
    3.) Provide insights into portfolio health, diversification, trade adjustments, etc.
    4.) Speculate on the market outlook based on current market conditions (price action, news, etc)
    5.) Identify market risks and suggest risk management strategies
    
    Here is my portfolio: {portfolio_data}

    Here are my open orders {open_orders}

    Overall, answer the following question with priority having that background: {message}

    """

    response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "system", "content": pre_prompt}]
    )
    return response.choices[0].message.content

def fetch_mock_api(symbol):
    return {
        "price" : 100
    }


class TradingBOTGUI:
    
    def __init__(self, root):
        self.root = root
        self.root.title("AI Trading Bot")
        self.equities = self.load_equities() #loads any previously saved stock symbols from a JSON file
        self. _running = False # a flag to track whether the bot is actively running

        #add equities to bot
        #Frame is container that holds widgets. Symbol and Entry box are placed side-by-side in grid layout
        self.form_frame = tk.Frame(root)
        self.form_frame.pack(pady=10)

        #Form to add new equity to trading bot
        tk.Label(self.form_frame, text="Symbol: ").grid(row=0, column=0)
        self.symbol_entry = tk.Entry(self.form_frame) #Fill in Entry Symbol
        self.symbol_entry.grid(row=0, column=1) #Fits in grid layout

        tk.Label(self.form_frame, text="Levels: ").grid(row=0, column=2)
        self.levels_entry = tk.Entry(self.form_frame)
        self.levels_entry.grid(row=0, column=3)

        #Drawdown: new entry at each 10%drop 
        tk.Label(self.form_frame, text="Drawdown%: ").grid(row=0, column=4)
        self.drawdown_entry = tk.Entry(self.form_frame)
        self.drawdown_entry.grid(row=0, column=5)

        self.add_button = tk.Button(self.form_frame, text="Add Equity", command=self.add_equity)
        self.add_button.grid(row=0, column=6)

        #Table to track the traded equities
        # API calls updates the table with our position, symbol, entry price, order status, etc 
        self.tree = ttk.Treeview(root, columns=("Symbol", "Position", "Entry Price", "Levels", "Status"), show='headings')
        headings = ["Symbol", "Position", "Entry Price", "Levels", "Status"]
        for col in headings:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120)
        self.tree.pack(pady=10)

        #Buttons to control the bot
        self.toggle_system_button = tk.Button(root, text="Toggle Selected System", command=self.toggle_selected_system)
        self.toggle_system_button.pack(pady=5)

        self.remove_button = tk.Button(root, text="Remove Selected Equity", command=self.remove_selected_equity)
        self.remove_button.pack(pady=5)

        #AI Component
        self.chat_frame = tk.Frame(root)
        self.chat_frame.pack(pady=10)

        self.chat_input = tk.Entry(self.chat_frame, width=50)
        self.chat_input.grid(row=0, column=0, padx=5)
        
        self.send_button = tk.Button(self.chat_frame, text="Send", command=self.send_message)
        self.send_button.grid(row=0, column=1)

        self.chat_output = tk.Text(root, height=5, width=60, state=tk.DISABLED)
        self.chat_output.pack() #Pack() shows the TKinter widget window

        #Functionalities
        #Load saved data
        self.refresh_table()

        #Auto-refreshing with data from API
        self.running = True
        self.auto_update_thread = threading.Thread(target=self.auto_update, daemon=True)
        self.auto_update_thread.start()

    #Functions
    def add_equity(self):
        symbol = self.symbol_entry.get().upper()
        levels = self.levels_entry.get()
        drawdown = self.drawdown_entry.get()

        if not symbol or not levels.isdigit() or not drawdown.replace('.', '', 1).isdigit():
            messagebox.showerror("Error", "Invalid Input")
            return

        levels = int(levels)
        drawdown = float(drawdown) /100
        entry_price = fetch_mock_api(symbol)['price']

        level_prices = {i+1 : round(entry_price * (1-drawdown*(i+1)), 2) for i in range(levels)}
        self.equities[symbol] = {
            "position": 0,
            "entry_price": entry_price,
            "levels": level_prices,
            "drawdown": drawdown,
            "status": "Off"
        }
        self.save_equities()
        self.refresh_table()

    def toggle_selected_system(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Warning", "No equity is Selected")
            return
        
        for item in selected_items:
            symbol = self.tree.item(item)['values'][0]
            self.equities[symbol]['status'] = "On" if self.equities[symbol]['status'] == "Off" else "Off"
            
        self.save_equities()
        self.refresh_table()

    def remove_selected_equity(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Warning", "No Equity Selected")
        
        for item in selected_items:
            symbol = self.tree.item(item)['values'][0]
            if symbol in self.equities:
                del self.equities[symbol]

        self.save_equities()
        self.refresh_table()

    def send_message(self):
        message = self.chat_input.get()
        if not message:
            return 

        response = LLM_response(message)

        self.chat_output.config(state=tk.NORMAL)
        self.chat_output.insert(tk.END, f'You: {message}\n{response}\n\n')
        self.chat_output.config(state=tk.DISABLED)
        self.chat_input.delete(0, tk.END)

    #Gets data of a Ticker-Symbol/Company from alpaca site
    def fetch_alpaca_data(self, symbol):
        try:
            barset = api.get_latest_trade(symbol)
            return {"price":barset.price}
        except Exception as e:
            return {"price":-1}

    #Checks if limit price of an order, is already in: 'placed-orders' list 
    def check_existing_orders(self, symbol, price):
        try:
            orders = api.list_orders(status='open', symbols=symbol)
            for order in orders:
                if float(order.limit_price) == price:
                    return True
        except Exception as e:
            messagebox.showerror("API Error", f"Error Checking Orders {e}")
        return False

    def get_max_entry_price(self, symbol):
        try:
            orders = api.list_orders(status="filled", limit=50)
            #prices = list[list of avg order prices, checks if order_avg_price = True, and order.symbol is correct]
            prices = [float(order.filled_avg_price) for order in orders if order.filled_avg_price and order.symbol == symbol]
            return max(prices) if prices else -1
        except Exception as e:
            messagebox.showerror("API Error", f"Error Fetching Orders {e}")
            return 0

    def trade_systems(self):
        for symbol, data in self.equities.items():
            if data['status'] == 'On':
                position_exists = False #initially positon doesn't exist
                #gets position, entry_price
                try:
                    position = api.get_position(symbol) #checks if a position exists in open-orders list
                    entry_price = self.get_max_entry_price(symbol)
                    position_exists = True #Now position exists
                #submits order if none exists already
                except Exception as e:
                    api.submit_order(
                        symbol=symbol,
                        qty=1,
                        side="buy",
                        type="market",
                        time_in_force="gtc",
                        extended_hours=True
                    )
                    messagebox.showinfo("Order Placed", f"Initial Order Placed for {symbol}")
                    
                    # entry_price = -1
                    # max_retries = 10        # try 10 times
                    # attempts = 0

                    # while entry_price == -1 and attempts < max_retries: #keeps waiting until entry_price != -1 (aka exists)
                    #     #entry_price = -1 if self.get_max_entry_price is called before order is filled.
                    #     entry_price = self.get_max_entry_price(symbol)
                    #     time.sleep(2)
                    #     attempts += 1
                    # if entry_price == -1:   # still failed after all retries
                    #     messagebox.showerror("Error", f"Could not get entry price for {symbol} after {max_retries} attempts")
                    #     continue            # skip to next symbol in the for loop
                    
                    #entry_price = -1 if self.get_max_entry_price is called before order is filled.
                    entry_price = self.get_max_entry_price(symbol)
                    time.sleep(2)
                    if entry_price == -1:
                        continue
                print(symbol, " entry_price: ", entry_price)
                
                #Creates level_prices based on entry_price, checks if prev levels of prices exists already
                level_prices = {i+1: round(entry_price*(1-data['drawdown']*(i+1)), 2) for i in range(len(data['levels']))}
                existing_levels = self.equities.get(symbol, {}).get('levels', {})
                for level, price in level_prices.items():
                    if level not in existing_levels and -(level) not in existing_levels:
                        existing_levels[level] = price

                #Update symbol data
                self.equities[symbol]['entry_price'] = entry_price
                self.equities[symbol]['levels'] = existing_levels
                self.equities[symbol]['position'] = 1 #Flag - active position

                if not position_exists:
                    for level, prices in level_prices.items():
                        self.place_order(symbol, prices, level)
                                    
            self.save_equities()
            self.refresh_table()
        else:
            return 

    def place_order(self, symbol, price, level):
        #if we have active order for that level, and we dont want to trade (String/Integer) (string = -"level") (integer: a key = -1)
        #update levels here, order is to be placed if level is pos, not placed if neg/open order exists already
        if -level in self.equities[symbol]['levels'] or '-1' in self.equities[symbol]['levels'].keys():
            return

        try:
            api.submit_order(
                symbol=symbol,
                qty=1,
                side = 'buy',
                type = 'limit',
                time_in_force='gtc',
                limit_price=price,
                extended_hours=True
            )
            self.equities[symbol]['levels'][-level] = price
            del self.equities[symbol]['levels'][level]
            print(f"Placed order for {symbol} @ {price}")
        except Exception as e:
            messagebox.showerror("Order Error", f"Error placing order {e}")

    def refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        #Update equities dictionary with live data
        for symbol, data in self.equities.items():
            self.tree.insert("", "end", values=(
            symbol,
            data['position'],
            data['entry_price'],
            str(data['levels']),
            data['status']
            ))

    
    def auto_update(self):
        while self.running:
            time.sleep(5)
            self.trade_systems()

    def save_equities(self):
        #open(file_action, wrx actions)
        with open(DATA_FILE, 'w') as f:
            json.dump(self.equities, f)
    
    def load_equities(self):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def on_close(self):
        self.running = False
        self.save_equities()
        self.root.destroy()
    

if __name__ == '__main__':
    root = tk.Tk()
    app = TradingBOTGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


  


        













