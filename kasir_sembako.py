import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime
import csv

DB = Path(__file__).with_name("kasir.db")

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, barcode TEXT UNIQUE, name TEXT NOT NULL, price INTEGER NOT NULL, stock INTEGER NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY, created TEXT, total INTEGER, paid INTEGER, change_due INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS sale_items(id INTEGER PRIMARY KEY, sale_id INTEGER, product_id INTEGER, name TEXT, qty INTEGER, price INTEGER, subtotal INTEGER)")
    c.commit()
    return c

def rp(n): return "Rp " + f"{int(n):,}".replace(",", ".")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Kasir Sembako")
        self.geometry("920x620")
        self.c = connect()
        self.cart = []
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=10, pady=10)
        self.sale = ttk.Frame(nb); self.stock = ttk.Frame(nb); self.hist = ttk.Frame(nb)
        nb.add(self.sale, text="Kasir"); nb.add(self.stock, text="Produk & Stok"); nb.add(self.hist, text="Riwayat")
        self.make_sale(); self.make_stock(); self.make_history()
        self.refresh_stock(); self.refresh_history()

    def make_sale(self):
        top=ttk.Frame(self.sale); top.pack(fill="x", pady=8)
        ttk.Label(top,text="Barcode / nama produk").pack(side="left")
        self.q=tk.StringVar(); e=ttk.Entry(top,textvariable=self.q,width=35); e.pack(side="left",padx=8)
        e.bind("<Return>",lambda _:self.add()); ttk.Button(top,text="Tambah",command=self.add).pack(side="left")
        self.cv=ttk.Treeview(self.sale,columns=("name","qty","price","sub"),show="headings",height=15)
        for c,t,w in [("name","Produk",350),("qty","Jumlah",80),("price","Harga",150),("sub","Subtotal",170)]:
            self.cv.heading(c,text=t); self.cv.column(c,width=w)
        self.cv.pack(fill="both",expand=True,pady=8)
        bar=ttk.Frame(self.sale);bar.pack(fill="x")
        self.total=ttk.Label(bar,text="Total: Rp 0",font=("Segoe UI",16,"bold"));self.total.pack(side="left")
        ttk.Button(bar,text="Hapus item",command=self.remove).pack(side="right")
        pay=ttk.Frame(self.sale);pay.pack(fill="x",pady=12)
        ttk.Label(pay,text="Uang diterima").pack(side="left")
        self.paid=tk.StringVar();ttk.Entry(pay,textvariable=self.paid,width=18).pack(side="left",padx=8)
        ttk.Button(pay,text="Selesaikan transaksi",command=self.checkout).pack(side="left")

    def make_stock(self):
        form=ttk.LabelFrame(self.stock,text="Tambah / perbarui produk");form.pack(fill="x",padx=10, pady=10)
        self.vars=[tk.StringVar() for _ in range(4)]
        for i,(label,var) in enumerate(zip(("Barcode","Nama","Harga jual","Stok"),self.vars)):
            ttk.Label(form,text=label).grid(row=0,column=i,padx=5)
            ttk.Entry(form,textvariable=var,width=21).grid(row=1,column=i,padx=5,pady=5)
        ttk.Button(form,text="Simpan",command=self.save_product).grid(row=1,column=4,padx=8)
        self.sv=ttk.Treeview(self.stock,columns=("barcode","name","price","stock"),show="headings")
        for c,t in [("barcode","Barcode"),("name","Nama produk"),("price","Harga"),("stock","Stok")]:
            self.sv.heading(c,text=t);self.sv.column(c,width=180)
        self.sv.pack(fill="both",expand=True,padx=10,pady=10)

    def make_history(self):
        ttk.Button(self.hist,text="Ekspor CSV",command=self.export).pack(anchor="e",padx=8)
        self.hv=ttk.Treeview(self.hist,columns=("id","date","total","paid","change"),show="headings")
        for c,t in [("id","No."),("date","Tanggal"),("total","Total"),("paid","Dibayar"),("change","Kembalian")]:
            self.hv.heading(c,text=t);self.hv.column(c,width=165)
        self.hv.pack(fill="both",expand=True,padx=10,pady=8)

    def refresh_stock(self):
        self.products=[dict(x) for x in self.c.execute("SELECT * FROM products ORDER BY name")]
        self.sv.delete(*self.sv.get_children())
        for p in self.products:self.sv.insert("","end",values=(p["barcode"],p["name"],rp(p["price"]),p["stock"]))

    def refresh_history(self):
        self.hv.delete(*self.hv.get_children())
        for r in self.c.execute("SELECT * FROM sales ORDER BY id DESC"):
            self.hv.insert("","end",values=(r["id"],r["created"],rp(r["total"]),rp(r["paid"]),rp(r["change_due"])))

    def save_product(self):
        try:
            barcode,name,price,stock=[v.get().strip() for v in self.vars]
            if not name: raise ValueError()
            price=int(price);stock=int(stock)
            if price<0 or stock<0:raise ValueError()
            if barcode:
                self.c.execute("INSERT INTO products(barcode,name,price,stock) VALUES(?,?,?,?) ON CONFLICT(barcode) DO UPDATE SET name=excluded.name,price=excluded.price,stock=excluded.stock",(barcode,name,price,stock))
            else:self.c.execute("INSERT INTO products(name,price,stock) VALUES(?,?,?)",(name,price,stock))
            self.c.commit()
            for v in self.vars:v.set("")
            self.refresh_stock()
        except (ValueError,sqlite3.IntegrityError):
            messagebox.showerror("Data tidak valid","Periksa nama, harga, stok, dan barcode. Harga/stok harus angka positif.")

    def add(self):
        q=self.q.get().strip()
        if not q:return
        p=self.c.execute("SELECT * FROM products WHERE barcode=? OR name LIKE ? ORDER BY name LIMIT 1",(q,"%"+q+"%")).fetchone()
        if not p:messagebox.showwarning("Tidak ditemukan","Produk tidak ditemukan.");return
        item=next((x for x in self.cart if x["id"]==p["id"]),None)
        if p["stock"]<=0 or (item and item["qty"]>=p["stock"]):
            messagebox.showwarning("Stok kurang","Stok produk tidak mencukupi.");return
        if item:item["qty"]+=1
        else:self.cart.append({"id":p["id"],"name":p["name"],"price":p["price"],"qty":1,"stock":p["stock"]})
        self.q.set("");self.refresh_cart()

    def refresh_cart(self):
        self.cv.delete(*self.cv.get_children())
        total=sum(x["qty"]*x["price"] for x in self.cart)
        for x in self.cart:self.cv.insert("","end",iid=str(x["id"]),values=(x["name"],x["qty"],rp(x["price"]),rp(x["qty"]*x["price"])))
        self.total.config(text="Total: "+rp(total))

    def remove(self):
        selected=self.cv.selection()
        if selected:
            self.cart=[x for x in self.cart if str(x["id"]) not in selected];self.refresh_cart()

    def checkout(self):
        if not self.cart:messagebox.showwarning("Kosong","Keranjang masih kosong.");return
        total=sum(x["qty"]*x["price"] for x in self.cart)
        try:paid=int(self.paid.get())
        except ValueError:messagebox.showerror("Pembayaran","Masukkan nominal uang diterima.");return
        if paid<total:messagebox.showerror("Pembayaran","Uang diterima kurang.");return
        try:
            with self.c:
                cur=self.c.execute("INSERT INTO sales(created,total,paid,change_due) VALUES(?,?,?,?)",(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),total,paid,paid-total))
                sid=cur.lastrowid
                for x in self.cart:
                    stock=self.c.execute("SELECT stock FROM products WHERE id=?",(x["id"],)).fetchone()["stock"]
                    if stock<x["qty"]:raise ValueError("Stok berubah, ulangi transaksi.")
                    self.c.execute("UPDATE products SET stock=stock-? WHERE id=?",(x["qty"],x["id"]))
                    self.c.execute("INSERT INTO sale_items(sale_id,product_id,name,qty,price,subtotal) VALUES(?,?,?,?,?,?)",(sid,x["id"],x["name"],x["qty"],x["price"],x["qty"]*x["price"]))
            lines=["TOKO SEMBAKO","Transaksi #"+str(sid),datetime.now().strftime("%d-%m-%Y %H:%M"),"-"*30]
            lines += [f'{x["name"]} x{x["qty"]}  {rp(x["qty"]*x["price"])}' for x in self.cart]
            lines += ["-"*30,"TOTAL "+rp(total),"DIBAYAR "+rp(paid),"KEMBALI "+rp(paid-total),"Terima kasih"]
            path=Path(__file__).with_name("struk_"+str(sid)+".txt");path.write_text("\n".join(lines),encoding="utf-8")
            messagebox.showinfo("Transaksi berhasil","\n".join(lines)+"\n\nStruk disimpan: "+path.name)
            self.cart=[];self.paid.set("");self.refresh_cart();self.refresh_stock();self.refresh_history()
        except ValueError as e:messagebox.showerror("Gagal",str(e))

    def export(self):
        path=Path(__file__).with_name("riwayat_transaksi.csv")
        with path.open("w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f);w.writerow(["No","Tanggal","Total","Dibayar","Kembalian"])
            for r in self.c.execute("SELECT * FROM sales ORDER BY id DESC"):w.writerow([r["id"],r["created"],r["total"],r["paid"],r["change_due"]])
        messagebox.showinfo("Selesai","CSV disimpan: "+str(path))

if __name__=="__main__": App().mainloop()
