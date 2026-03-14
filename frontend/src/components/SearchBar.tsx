import { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import Dropdown from './Dropdown';
import { fetchSearchSuggestions } from '../api/api';
import type { SearchSuggestion } from '../api/api';
import './SearchBar.css';

const searchOptions = [
  { value: 'Professor', label: 'Professor' },
  { value: 'Course', label: 'Course' },
];

const SearchBar = () => {
  const navigate = useNavigate();
  const [searchType, setSearchType] = useState('Professor');
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [isFocused, setIsFocused] = useState(false);
  const [placeholder, setPlaceholder] = useState('');
  
  const wrapperRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const professorExamples = useMemo(() => [
    "John Doe", "Jane Smith", "Alan Mislove", "Ravi Sundaram", 
    "Dan Felushko", "Ousmane Hicham", "Cristina Nita-Rotaru",
    "Stacy Marsella", "Kathleen Durant", "Gene Cooperman"
  ], []);

  const courseExamples = useMemo(() => [
    "CS 2500", "CS 3500", "CS 4500", "ECON 1115", "MATH 1341",
    "CY 2550", "PHYS 1161", "ACCT 1201", "MKTG 2101", "BIOL 1111"
  ], []);

  // Typing animation logic
  useEffect(() => {
    if (isFocused || query) {
      setPlaceholder(searchType === 'Professor' ? 'Search by professor name...' : 'Search by course name or code...');
      return;
    }

    const examples = searchType === 'Professor' ? professorExamples : courseExamples;
    let currentExampleIndex = Math.floor(Math.random() * examples.length);
    let currentText = "";
    let isDeleting = false;
    let typingSpeed = 100;

    const type = () => {
      const fullText = examples[currentExampleIndex];
      
      if (isDeleting) {
        currentText = fullText.substring(0, currentText.length - 1);
        typingSpeed = 50;
      } else {
        currentText = fullText.substring(0, currentText.length + 1);
        typingSpeed = 100;
      }

      setPlaceholder(`Search for "${currentText}"`);

      if (!isDeleting && currentText === fullText) {
        isDeleting = true;
        typingSpeed = 2000; // Pause at end
      } else if (isDeleting && currentText === "") {
        isDeleting = false;
        currentExampleIndex = (currentExampleIndex + 1) % examples.length;
        typingSpeed = 500; // Pause before next
      }

      timeoutId = setTimeout(type, typingSpeed);
    };

    let timeoutId = setTimeout(type, typingSpeed);
    return () => clearTimeout(timeoutId);
  }, [isFocused, query, searchType, professorExamples, courseExamples]);

  const handleSearchTypeChange = (newType: string) => {
    setSearchType(newType);
    setQuery('');
    setSuggestions([]);
    setShowSuggestions(false);
  };

  // Debounced fetch
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    const trimmedQuery = query.trim();
    if (trimmedQuery.length < 2) {
      // Don't call setState here if it's already empty/false
      // But we need to handle it. Actually, the lint error is specific to SYNC calls in body.
      // We can use an async or just handle it.
      return;
    }

    debounceRef.current = setTimeout(async () => {
      try {
        const results = await fetchSearchSuggestions(trimmedQuery, searchType);
        const limitedResults = searchType === 'Professor' ? results.slice(0, 3) : results;
        setSuggestions(limitedResults);
        setShowSuggestions(limitedResults.length > 0);
        setActiveIndex(-1);
      } catch {
        setSuggestions([]);
        setShowSuggestions(false);
      }
    }, 200);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, searchType]);

  // Handle query change to sync suggestions state
  const handleQueryChange = (val: string) => {
    setQuery(val);
    if (val.trim().length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Removed redundant clear effect

  const handleSelect = (suggestion: SearchSuggestion) => {
    setShowSuggestions(false);
    if (suggestion.type === 'professor') {
      const slug = suggestion.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      navigate(`/professors/${slug}`);
    } else {
      const code = suggestion.code.toLowerCase();
      navigate(`/courses/${code}`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showSuggestions || suggestions.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((prev) => {
        const next = prev < suggestions.length - 1 ? prev + 1 : 0;
        document.querySelector(`.suggestion-item:nth-child(${next + 1})`)?.scrollIntoView({ block: 'nearest' });
        return next;
      });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((prev) => {
        const next = prev > 0 ? prev - 1 : suggestions.length - 1;
        document.querySelector(`.suggestion-item:nth-child(${next + 1})`)?.scrollIntoView({ block: 'nearest' });
        return next;
      });
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault();
      handleSelect(suggestions[activeIndex]);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  return (
    <div className="search-wrapper" ref={wrapperRef}>
      <div className="search-bar">
        <div onMouseDown={() => setShowSuggestions(false)}>
          <Dropdown
            className="search-dropdown"
            options={searchOptions}
            value={searchType}
            onChange={handleSearchTypeChange}
          />
        </div>

        <div className="search-divider" />

        <span className="search-icon">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </span>

        <input
          className="search-input"
          type="text"
          placeholder={placeholder}
          value={query}
          onChange={(e) => handleQueryChange(e.target.value)}
          onFocus={() => {
            setIsFocused(true);
            if (suggestions.length > 0) setShowSuggestions(true);
          }}
          onBlur={() => setIsFocused(false)}
          onKeyDown={handleKeyDown}
        />
      </div>

      {showSuggestions && (
        <ul className="search-suggestions">
          {suggestions.map((s, i) => (
            <li
              key={s.type === 'professor' ? s.name : s.code}
              className={`suggestion-item ${i === activeIndex ? 'active' : ''}`}
              onClick={() => handleSelect(s)}
              onMouseEnter={() => setActiveIndex(i)}
            >
              {s.type === 'professor' ? (
                <>
                  <div className="suggestion-main">
                    <span className="suggestion-name">{s.name}</span>
                    <span className="suggestion-dept">{s.dept}</span>
                  </div>
                  {s.rating !== null && (
                    <span className="suggestion-rating">{s.rating.toFixed(2)}</span>
                  )}
                </>
              ) : (
                <div className="suggestion-main">
                  <span className="suggestion-name">
                    <span className="suggestion-code">{s.code}</span>
                    {' '}{s.name}
                  </span>
                  <span className="suggestion-dept">{s.dept}</span>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default SearchBar;