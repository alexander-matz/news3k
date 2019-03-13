package main;

import (
	"flag"
	"fmt"
	"log"
	"net/http"
	"encoding/base64"
	"encoding/binary"
	"html/template"
	"time"
	"strings"
	"errors"

	"database/sql"
	_ "github.com/mattn/go-sqlite3"
)

type Config struct {
	Prefix string
	Address string
	TemplDir string
	StaticDir string
	DbPath string
	Items int
}

type Instance struct {
	db *sql.DB
	server *http.Server
	enc *base64.Encoding
	cfg *Config
	rootTemplate *template.Template
	artTemplate *template.Template
}

func NewInstance(cfg *Config) *Instance {
	alpha := "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
	encoding := base64.NewEncoding(alpha).WithPadding(base64.NoPadding)
	s := &Instance{
		cfg: cfg,
		enc: encoding,
	}
	return s
}

func (s *Instance) Start() {
	log.Printf("Starting server...")
	log.Printf("URL prefix: %s", s.cfg.Prefix)
	log.Printf("Database path: %s", s.cfg.DbPath)

	s.setupTemplates()

	db, err := sql.Open("sqlite3", s.cfg.DbPath)
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	s.db = db

	http.Handle(s.url("/"), s.makeRootHandler())
	http.Handle(s.url("/article/"), s.makeArticleHandler("/article/"))
	http.Handle(s.url("/static/"), s.makeStaticHandler("/static/"))

	log.Fatal(http.ListenAndServe(s.cfg.Address, nil))
}

func (s *Instance) url(path string) string {
	return s.cfg.Prefix + path
}

func (s *Instance) b64enc(num uint64) string {
	data := make([]byte, 8)
	binary.BigEndian.PutUint64(data, num)
	return s.enc.EncodeToString(data)
}

func (s *Instance) b64dec(str string) (uint64, error) {
	data, err := s.enc.DecodeString(str)
	if (err != nil) {
		return 0, err
	}
	if len(data) > 8 {
		return 0, errors.New("Encoded string too large")
	}
	pad := make([]byte, 8-len(data))
	data = append(pad, data...)
	return binary.BigEndian.Uint64(data), nil
}

func (s *Instance) setupTemplates() {
	funcs := template.FuncMap{
		"url": func(url string) string { return s.url(url) },
		"b64enc": func(i uint64) string { return s.b64enc(i) },
		"now": time.Now,
		"split": func(s string) []string { return strings.Split(s, "\n") },
	}
	rootTemplate, err := template.New("root.gohtml").Funcs(funcs).
		ParseFiles(s.cfg.TemplDir + "/root.gohtml")
	if err != nil {
		log.Fatal(err)
	}
	s.rootTemplate = rootTemplate
	artTemplate, err := template.New("article.gohtml").Funcs(funcs).
		ParseFiles(s.cfg.TemplDir + "/article.gohtml")
	if err != nil {
		log.Fatal(err)
	}
	s.artTemplate = artTemplate
}

func (s *Instance) makeStaticHandler(route string) http.Handler {
	fs := http.FileServer(http.Dir(s.cfg.StaticDir))
	return http.StripPrefix(s.url(route), fs)
}

func (s *Instance) makeRootHandler() http.Handler {
	listStmt, err := s.db.Prepare("SELECT a.url, a.handle, a.title, " +
		"a.summary, a.found_at, s.url AS srcurl, s.brand " +
		"FROM articles AS a " +
		"LEFT JOIN sources AS s ON a.source = s.id " +
		"WHERE title IS NOT NULL " +
		"  AND a.text IS NOT NULL AND LENGTH(a.text) >= 140 " +
		"ORDER BY a.found_at DESC, a.handle DESC LIMIT ?;")
	if err != nil {
		log.Fatal(err)
	}

	fn := func (w http.ResponseWriter, r *http.Request) {
		rows, err := listStmt.Query(s.cfg.Items);
		if err != nil {
			fmt.Fprintf(w, "Database Error")
		}
		defer rows.Close()
		type Article struct {
			Url string
			Handle uint64
			Title string
			Summary string
			FoundAt time.Time
			SrcUrl string
			Brand string
		}
		articles := make([]Article, 0)

		for rows.Next() {
			var a Article
			if err := rows.Scan(&a.Url, &a.Handle, &a.Title, &a.Summary, &a.FoundAt, &a.SrcUrl, &a.Brand); err != nil {
				log.Print(err)
				continue
			}
			articles = append(articles, a)
		}
		err = s.rootTemplate.Execute(w, articles)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
		}
	}
	return http.HandlerFunc(fn)
}

func (s *Instance) makeArticleHandler(route string) http.Handler {
	baseLen := len(s.url(route))
	artStmt, err := s.db.Prepare("SELECT a.url, a.handle, a.title, " +
		"a.found_at, a.text, s.url AS srcurl, s.brand " +
		"FROM articles AS a " +
		"LEFT JOIN sources AS s ON a.source = s.id " +
		"WHERE a.handle = ? " +
		"LIMIT 1;")
	if err != nil {
		log.Fatal(err)
	}
	_ = artStmt

	fn := func (w http.ResponseWriter, r *http.Request) {
		article := r.URL.Path[baseLen:]
		handle, err := s.b64dec(article)
		if err != nil {
			log.Print(err)
			fmt.Fprintf(w, "article not found")
			return
		}
		rows, err := artStmt.Query(handle);
		if err != nil {
			log.Print(err)
			fmt.Fprintf(w, "database error")
			return
		}
		defer rows.Close()
		if !rows.Next() {
			log.Printf("invalid article handle: %s", article)
			fmt.Fprintf(w, "article not found")
			return
		}
		var a struct{
			Url string
			Handle string
			Title string
			FoundAt time.Time
			Text string
			SrcUrl string
			Brand string
		}
		if err = rows.Scan(&a.Url, &a.Handle, &a.Title, &a.FoundAt, &a.Text, &a.SrcUrl, &a.Brand); err != nil {
			log.Print(err)
			fmt.Fprintf(w, "database error")
			return
		}
		s.artTemplate.Execute(w, a)
	}
	return http.HandlerFunc(fn)
}

func main() {
	prefix := flag.String("prefix", "", "url prefix")
	address := flag.String("address", ":5000", "binding address")
	templdir := flag.String("templates", "templates", "template directory")
	staticdir := flag.String("static", "static", "static files directory")
	dbpath := flag.String("dbpath", "news.sqlite", "path to sqlite database")
	items := flag.Int("items", 200, "items on front page")

	flag.Parse()

	instance := NewInstance(&Config{
		Prefix: *prefix,
		Address: *address,
		TemplDir: *templdir,
		StaticDir: *staticdir,
		DbPath: *dbpath,
		Items: *items,
	})

	instance.Start()
}
